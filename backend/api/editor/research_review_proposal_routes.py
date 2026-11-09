"""Native review proposal lifecycle; authenticated UI alone can accept or reject."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.api.editor.research_routes import _authorize, _workspace
from backend.editor.research import model, review_proposals


def create_research_review_proposal_router(service):
    router = APIRouter(prefix="/api/research/review-proposals", tags=["research"])

    def call(request, project, workspace, write, operation):
        try:
            selected = _workspace(service, project, workspace)
            actor, name = _authorize(service, request, project, selected, write)
            return operation(selected, actor, name)
        except model.GateError as error:
            return JSONResponse(error.body(), status_code=error.status)

    @router.post("")
    def prepare(request: Request, payload: dict):
        def run(workspace, actor, name):
            model.shape(payload, {"project", "workspace", "review", "requestId"})
            return review_proposals.prepare(service, payload["project"], workspace, payload["review"], payload["requestId"], actor, name)
        return call(request, payload.get("project"), payload.get("workspace"), True, run)

    @router.get("")
    def listing(request: Request, project: str, workspace: str, decisionId: str):
        return call(request, project, workspace, False, lambda selected, actor, name: review_proposals.listing(service, project, selected, decisionId))

    @router.get("/{identifier}")
    def read(request: Request, project: str, workspace: str, identifier: str):
        return call(request, project, workspace, False, lambda selected, actor, name: review_proposals.read(service, project, selected, identifier))

    @router.post("/{identifier}/{action}")
    def decide(request: Request, identifier: str, action: str, payload: dict):
        def run(workspace, actor, name):
            model.shape(payload, {"project", "workspace", "digest"})
            return review_proposals.decide(service, payload["project"], workspace, identifier, payload["digest"], action, actor)
        return call(request, payload.get("project"), payload.get("workspace"), True, run)

    return router
