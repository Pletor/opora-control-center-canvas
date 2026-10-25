"""Bounded pre-claim kit preview; identity is required but no execution is granted."""
import sqlite3

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.canvas.opora_execution_observer_auth import strict_json
from backend.library.harness_preflight import preview


def create_harness_preflight_router(canvas):
    router = APIRouter()
    headers = {"Cache-Control": "no-store"}

    @router.post("/harness-preflight")
    async def preflight(request: Request):
        if getattr(request.state, "actor", None) not in ("human", "agent"):
            return JSONResponse({"error": "Execution identity is required."}, status_code=428, headers=headers)
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 4096:
                return JSONResponse({"error": "Preflight request exceeds 4096 bytes."}, status_code=413, headers=headers)
            body.extend(chunk)
        try:
            result = await run_in_threadpool(preview, canvas, strict_json(bytes(body)))
            return JSONResponse(result, headers=headers)
        except (ValueError, KeyError, TypeError, sqlite3.OperationalError):
            return JSONResponse({"error": "Accepted preflight context is unavailable or changed; negotiate context first."},
                                status_code=409, headers=headers)

    return router
