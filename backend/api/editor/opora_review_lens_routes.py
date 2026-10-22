"""PR Lens review evidence (docs/oporahub-review-jobs.md, "Diagram PR Lens"): optional, never blocking."""
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from backend.canvas import opora_review_lens as review_lens
from backend.canvas.opora_execution_validation import validate
from backend.canvas.opora_review_jobs import ReviewJobService

SCOPE = {"min_length": 1, "max_length": 64}


def create_review_lens_router(service, jobs=None):
    router = APIRouter(prefix="/api/oporahub", tags=["oporahub"])
    addenda = review_lens.LensAddenda(jobs or ReviewJobService(service))

    def identity(request):
        actor, name = request.state.actor, getattr(request.state, "agent", None)
        if actor not in ("human", "agent") or (actor == "agent" and (not isinstance(name, str) or not name.strip())):
            return None
        return "agent:" + name if actor == "agent" else "human"

    @router.post("/review-jobs/lens")
    def submit(payload: dict, request: Request):
        by = identity(request)
        if by is None:
            return JSONResponse({"error": "Review identity is required.", "code": "identity_required"}, status_code=428)
        try:
            return addenda.submit(payload, by)
        except ValueError as exc:
            return JSONResponse({"error": str(exc), "code": "review_conflict"}, status_code=409)

    @router.get("/review-lens")
    def read(request: Request, project: str = Query(**SCOPE), workspace: str = Query(**SCOPE),
             nodeId: str = Query(min_length=1, max_length=80)):
        if identity(request) is None:
            return JSONResponse({"error": "Review identity is required.", "code": "identity_required"}, status_code=428)
        try:
            validate({"project": project, "workspace": workspace, "nodeId": nodeId}, {"nodeId"})
        except ValueError as exc:
            return JSONResponse({"error": str(exc), "code": "invalid_request"}, status_code=400)
        with service.graph_lock_for(project), service.lock_for(project):
            return review_lens.for_node(service.db_for(project), project, workspace, nodeId)

    return router
