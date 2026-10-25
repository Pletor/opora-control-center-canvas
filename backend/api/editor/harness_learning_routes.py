"""Read-only scoped measurements. Workers have no endpoint for asserting verified evidence."""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from backend.api.editor.harness_kit_capabilities_routes import (
    create_harness_kit_capabilities_router,
)
from backend.api.editor.harness_origin_routes import create_harness_origin_router
from backend.api.editor.harness_preflight_routes import create_harness_preflight_router
from backend.api.editor.harness_recovery_routes import create_harness_recovery_router
from backend.api.editor.harness_shared_memory_routes import create_harness_shared_memory_router
from backend.canvas.opora_change_validation import scope
from backend.library.harness_learning_rates import read
from database.repositories.harness_memory import status as memory_status


def create_harness_learning_router(canvas):
    router = APIRouter(prefix="/api/oporahub", tags=["oporahub"])

    @router.get("/harness-learning")
    def learning(project: str, workspace: str, nodeId: str | None = None,
                 resource: str | None = None, limit: int = Query(100, ge=1, le=100)):
        try:
            scope({"project": project, "workspace": workspace})
            for value in (nodeId, resource):
                if value is not None and (not value or len(value) > 200 or any(ord(c) < 32 for c in value)):
                    raise ValueError("Invalid Harness measurement filter.")
        except ValueError as error:
            return JSONResponse({"error": str(error), "code": "invalid_scope"}, status_code=422)
        if not canvas.project_exists(project):
            return JSONResponse({"error": "Project does not exist.", "code": "project_not_found"}, status_code=404)
        with canvas.lock_for(project):
            db = canvas.db_for(project)
            return read(db, project, workspace, node=nodeId, resource=resource, limit=limit)

    @router.get("/harness-memory")
    def delivery(project: str, workspace: str, limit: int = Query(100, ge=1, le=100)):
        try:
            scope({"project": project, "workspace": workspace})
        except ValueError as error:
            return JSONResponse({"error": str(error), "code": "invalid_scope"}, status_code=422)
        if not canvas.project_exists(project):
            return JSONResponse({"error": "Project does not exist.", "code": "project_not_found"}, status_code=404)
        with canvas.lock_for(project):
            return memory_status(canvas.db_for(project), project, workspace, limit)

    router.include_router(create_harness_recovery_router(canvas))
    router.include_router(create_harness_origin_router(canvas))
    router.include_router(create_harness_preflight_router(canvas))
    router.include_router(create_harness_kit_capabilities_router(canvas))
    router.include_router(create_harness_shared_memory_router(canvas))
    return router
