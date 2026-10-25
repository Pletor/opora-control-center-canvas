"""Domain-owned read-only endpoint for pinned paired evaluation metadata."""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from backend.canvas.opora_change_validation import scope
from backend.library.harness_paired_reports import read


def create_harness_paired_router(canvas):
    router = APIRouter(tags=["oporahub"])

    @router.get("/harness-paired-evaluations")
    def evaluations(project: str, workspace: str, nodeId: str | None = None,
                    resource: str | None = None, problem: str | None = None,
                    limit: int = Query(20, ge=1, le=100)):
        try:
            scope({"project": project, "workspace": workspace})
            for value in (nodeId, resource, problem):
                if value is not None and (not value or len(value) > 200 or any(ord(c) < 32 for c in value)):
                    raise ValueError("Invalid Harness paired filter.")
        except ValueError as error:
            return JSONResponse({"error": str(error), "code": "invalid_scope"}, status_code=422)
        if not canvas.project_exists(project):
            return JSONResponse({"error": "Project does not exist.", "code": "project_not_found"}, status_code=404)
        with canvas.lock_for(project):
            return read(canvas.db_for(project), project, workspace, node=nodeId, resource=resource,
                        problem=problem, limit=limit)

    return router
