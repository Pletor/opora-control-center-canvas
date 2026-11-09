"""Scoped library review reads and explicit human decisions."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from backend.api.editor.research_routes import _authorize
from backend.brain_opora.determinism.gate_payloads import GateError

from backend.canvas.activity_log import require_human
from backend.flow import library_reviews
from backend.flow.workflows import FlowNotFound


def create_library_review_router(service):
    router = APIRouter(prefix="/api/library/reviews", tags=["library"])

    @router.get("")
    def reviews(request: Request, project: str, workspace: str):
        try:
            _authorize(service, request, project, workspace)
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)
        with service.registry_lock:
            return library_reviews.listing(service, project, workspace)

    @router.get("/{identifier}")
    def review(identifier: str, request: Request, project: str, workspace: str):
        try:
            _authorize(service, request, project, workspace)
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)
        with service.registry_lock:
            try:
                return library_reviews.read(service, project, workspace, identifier)
            except FlowNotFound as error:
                raise HTTPException(404, str(error)) from error

    @router.post("/{identifier}/{action}")
    def decide(identifier: str, action: str, payload: dict, request: Request):
        require_human(getattr(request.state, "actor", None), "O knihovně člověka rozhoduje člověk v UI.")
        if set(payload) != {"project", "workspace"}:
            raise ValueError("Library review requires project and workspace.")
        return library_reviews.decide(service, payload["project"], payload["workspace"], identifier, action)

    return router
