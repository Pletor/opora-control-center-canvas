"""Local policy API; human identity is established by middleware, never request JSON."""
from fastapi import APIRouter, Query, Request

from backend.canvas.activity_log import require_human
from backend.canvas.opora_review_policy import OporaReviewPolicy


def create_opora_review_policy_router(service):
    router = APIRouter(prefix="/api/oporahub/review-policy", tags=["oporahub"])
    policy = OporaReviewPolicy(service)

    def author(request):
        require_human(request.state.actor, "Review policy changes require a human UI session.")
        return {"kind": "human", "name": "Člověk"}

    @router.get("")
    def current(request: Request, project: str, workspace: str):
        return policy.context(project, workspace, actor=request.state.actor)

    @router.get("/history")
    def history(project: str, workspace: str):
        return policy.history(project, workspace)

    @router.get("/status")
    def status(project: str, workspace: str, prNumber: int = Query(ge=1, le=2147483647)):
        return policy.status(project, workspace, prNumber)

    @router.post("")
    def configure(payload: dict, request: Request):
        return policy.configure(payload, author(request))

    @router.post("/disable")
    def disable(payload: dict, request: Request):
        return policy.disable(payload, author(request))

    return router
