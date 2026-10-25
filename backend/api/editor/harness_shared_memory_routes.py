"""Reference-only shared lesson publication and fresh exact OpenViking readback."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.canvas.opora_execution_observer_auth import strict_json
from backend.integrations.openviking_client import OpenVikingUnavailable
from backend.library import harness_shared_memory as shared


def create_harness_shared_memory_router(canvas):
    router = APIRouter(prefix="/harness-shared-memory", tags=["oporahub"])

    async def invoke(request, operation):
        if getattr(request.state, "actor", None) not in ("human", "agent"):
            return JSONResponse({"error": "Execution identity is required."}, status_code=428)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 4096:
                return JSONResponse({"error": "Shared memory request exceeds 4096 bytes."}, status_code=413)
        try:
            payload = strict_json(bytes(body))
            if not isinstance(payload, dict) or set(payload) != {"publication"}:
                raise ValueError("Only a publication reference is accepted.")
            return await run_in_threadpool(operation, canvas, payload["publication"])
        except (ValueError, KeyError, TypeError, OpenVikingUnavailable):
            return JSONResponse({"error": "Shared memory is unavailable or its evidence changed."}, status_code=409)

    @router.post("/publish")
    async def publish(request: Request):
        return await invoke(request, shared.enqueue)

    @router.post("/recall")
    async def recall(request: Request):
        return await invoke(request, shared.recall)

    return router
