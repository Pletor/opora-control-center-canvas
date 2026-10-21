"""Per-head self-check evidence for the merge gate (docs/oporahub-review-jobs.md, "Důkaz vlastních kontrol")."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.canvas.opora_review_jobs import ReviewJobsDisabled, ReviewJobService
from backend.canvas.opora_review_self_checks import SelfCheckAddenda


def create_review_self_check_router(service, jobs=None):
    router = APIRouter(prefix="/api/oporahub/review-jobs", tags=["oporahub"])
    addenda = SelfCheckAddenda(jobs or ReviewJobService(service))

    @router.post("/self-checks")
    def submit(payload: dict, request: Request):
        actor, name = request.state.actor, getattr(request.state, "agent", None)
        if actor not in ("human", "agent") or (actor == "agent" and (not isinstance(name, str) or not name.strip())):
            return JSONResponse({"error": "Review identity is required.", "code": "identity_required"}, status_code=428)
        try:
            return addenda.submit(payload, "agent:" + name if actor == "agent" else "human")
        except ReviewJobsDisabled as exc:
            return JSONResponse({"error": str(exc), "code": "review_jobs_disabled"}, status_code=409)
        except ValueError as exc:
            return JSONResponse({"error": str(exc), "code": "review_conflict"}, status_code=409)

    return router
