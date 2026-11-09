"""Exact scoped native working-graph/removal review; human actions stay explicit."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.api.editor.research_routes import _authorize
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.editor.node import removal_reviews
from backend.editor.research.model import identifier as valid_identifier


def create_working_review_router(service):
    router = APIRouter(prefix="/api/working-reviews", tags=["working-review"])

    def call(request, project, workspace, write, action):
        try:
            valid_identifier(project); valid_identifier(workspace)
            actor, name = _authorize(service, request, project, workspace, write)
            return action({"kind": actor, "name": name or "UI"})
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)

    @router.get("/{operation}/{identifier}")
    def read(operation: str, identifier: str, request: Request, project: str, workspace: str):
        return call(request, project, workspace, False,
                    lambda actor: removal_reviews.read(service, project, workspace, operation, identifier))

    @router.post("/{operation}/{identifier}/apply")
    def apply(operation: str, identifier: str, request: Request, payload: dict):
        if set(payload) != {"project", "workspace"}:
            raise ValueError("Expected project and workspace.")
        return call(request, payload["project"], payload["workspace"], True,
                    lambda actor: removal_reviews.apply(service, payload["project"], payload["workspace"], operation, identifier, actor))
    return router
