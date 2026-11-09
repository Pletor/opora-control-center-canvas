"""Exact scoped vault intent reads and actual human execution of native operations."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.api.editor.brief_vault_routes import _bad_request
from backend.api.editor.research_routes import _authorize
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.payload_errors import InvalidPayload
from backend.editor.brief_vault import operation_reviews


def create_brief_vault_review_router(service):
    router = APIRouter(prefix="/api/brief-vault/reviews", tags=["brief-vault"])

    @router.get("/{identifier}")
    def read(request: Request, identifier: str, project: str, workspace: str):
        try:
            _authorize(service, request, project, workspace)
            return operation_reviews.read(service, project, workspace, identifier)
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)

    @router.post("/{identifier}/{action}")
    def decide(request: Request, identifier: str, action: str, payload: dict):
        if set(payload) != {"project", "workspace", "digest"}:
            raise InvalidPayload("Expected project, workspace and exact intent digest.", field="payload")
        try:
            actor, _ = _authorize(service, request, payload["project"], payload["workspace"], True)
            return _bad_request(lambda: operation_reviews.decide(service, payload["project"], payload["workspace"],
                identifier, payload["digest"], action, actor))
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)

    return router
