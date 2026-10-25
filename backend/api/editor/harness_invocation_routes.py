"""Read-only worker-reported invocation measurements, scoped like Harness acceptance rates."""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from backend.api.editor.harness_documentation_routes import create_harness_documentation_router
from backend.api.editor.harness_paired_routes import create_harness_paired_router
from backend.canvas.opora_change_validation import scope
from backend.library.harness_invocation_reports import read


def create_harness_invocation_router(canvas):
    router = APIRouter(prefix="/api/oporahub", tags=["oporahub"])

    @router.get("/harness-invocations")
    def invocations(project: str, workspace: str, nodeId: str | None = None,
                    resource: str | None = None, limit: int = Query(50, ge=1, le=100)):
        try:
            scope({"project": project, "workspace": workspace})
            for value in (nodeId, resource):
                if value is not None and (not value or len(value) > 200 or any(ord(c) < 32 for c in value)):
                    raise ValueError("Invalid Harness invocation filter.")
        except ValueError as error:
            return JSONResponse({"error": str(error), "code": "invalid_scope"}, status_code=422)
        if not canvas.project_exists(project):
            return JSONResponse({"error": "Project does not exist.", "code": "project_not_found"}, status_code=404)
        with canvas.lock_for(project):
            return read(canvas.db_for(project), project, workspace, node=nodeId, resource=resource, limit=limit)

    router.include_router(create_harness_paired_router(canvas))
    router.include_router(create_harness_documentation_router(canvas))
    return router
