"""Independent broker writes retain the app's normal Host/Origin/session boundary."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.canvas.opora_execution_observer_auth import BODY_LIMIT, authenticate
from backend.canvas.opora_execution_observers import ExecutionObservers


def create_execution_observer_router(canvas):
    router = APIRouter(prefix="/api/oporahub/execution-observers", tags=["oporahub"])
    service = ExecutionObservers(canvas)

    async def write(request, action):
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > BODY_LIMIT:
                return JSONResponse({"error": "Observer body exceeds its limit."}, status_code=413)
            body.extend(chunk)
        raw = bytes(body)
        try:
            observer_id, config, payload = authenticate(request.headers, raw)
            return action(payload, observer_id, config)
        except PermissionError:
            return JSONResponse({"error": "Observer authentication failed.", "code": "observer_authentication_failed"}, status_code=403)
        except (ValueError, TypeError, KeyError):
            return JSONResponse({"error": "Observer evidence was rejected.", "code": "observer_conflict"}, status_code=409)

    @router.post("/intents")
    async def bind(request: Request):
        return await write(request, service.bind)

    @router.post("/observations")
    async def observe(request: Request):
        return await write(request, service.observe)

    @router.get("")
    def summary(project: str, workspace: str, request: Request, limit: int = 100):
        if request.state.actor not in {"human", "agent"}:
            return JSONResponse({"error": "Execution observation reader identity is required.", "code": "identity_required"}, status_code=428)
        try:
            return service.summary(project, workspace, limit=limit)
        except (ValueError, TypeError, KeyError):
            return JSONResponse({"error": "Observer history is unavailable in this scope.", "code": "observer_conflict"}, status_code=409)

    return router
