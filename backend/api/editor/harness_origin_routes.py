"""Read-only historical origin comparison; never reclassify using today's graph."""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from backend.canvas.opora_change_validation import scope
from backend.library.harness_origin_history import read


def create_harness_origin_router(canvas):
    router = APIRouter()

    @router.get("/harness-origin-history")
    def history(project: str, workspace: str, nodeId: str | None = None,
                resource: str | None = None, originScope: str | None = None,
                originNode: str | None = None, limit: int = Query(100, ge=1, le=100)):
        try:
            scope({"project": project, "workspace": workspace})
            for value, maximum in ((nodeId, 200), (resource, 200), (originNode, 1024)):
                if value is not None and (not value or len(value) > maximum
                                          or any(ord(char) < 32 for char in value)):
                    raise ValueError("Invalid Harness origin filter.")
            if not canvas.project_exists(project):
                return JSONResponse({"error": "Project does not exist."}, status_code=404)
            with canvas.lock_for(project):
                value = read(canvas.db_for(project), project, workspace, node=nodeId,
                             resource=resource, origin_scope=originScope,
                             origin_node=originNode, limit=limit)
            return JSONResponse(value, headers={"Cache-Control": "no-store"})
        except ValueError as error:
            return JSONResponse({"error": str(error)}, status_code=422)

    return router
