"""Credentialed recovery preview; no file restoration or specification acceptance."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.canvas.opora_execution_observer_auth import strict_json
from backend.library.harness_recovery import HarnessRecovery


def create_harness_recovery_router(canvas):
    router = APIRouter()
    recovery = HarnessRecovery(canvas)

    @router.post("/harness-recovery")
    async def preview(request: Request):
        if getattr(request.state, "actor", None) not in ("human", "agent"):
            return JSONResponse({"error": "Execution identity is required."}, status_code=428)
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 4096:
                return JSONResponse({"error": "Recovery request exceeds 4096 bytes."}, status_code=413)
            body.extend(chunk)
        try:
            return await run_in_threadpool(recovery.preview, strict_json(bytes(body)))
        except (ValueError, KeyError, TypeError):
            return JSONResponse({"error": "Recovery is unavailable, incompatible or unauthorized."}, status_code=409)

    return router
