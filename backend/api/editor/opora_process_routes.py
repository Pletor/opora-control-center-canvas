"""Live orientation reads only; no process-state transitions or execution preparation."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.canvas.opora_process_sync import ProcessSync


def create_opora_process_router(canvas):
    router = APIRouter(prefix="/api/oporahub/process", tags=["oporahub"])
    process = ProcessSync(canvas)

    @router.get("")
    def read(project: str, workspace: str, nodeId: str | None = None):
        try:
            return process.read(project, workspace, nodeId)
        except ValueError as error:
            return JSONResponse({"error": str(error), "code": "process_unavailable"}, status_code=409)

    return router
