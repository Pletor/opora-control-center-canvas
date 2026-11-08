"""Scoped bridge from existing Office feedback to research and back."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.api.editor.research_routes import _authorize, _workspace
from backend.editor.research import model, ticket_bridge


def create_research_ticket_router(service):
    router = APIRouter(prefix="/api/research/tickets", tags=["research"])

    def call(request, payload, operation):
        try:
            model.identifier(payload.get("project"))
            workspace = _workspace(service, payload["project"], payload.get("workspace"))
            actor, agent = _authorize(service, request, payload["project"], workspace, True)
            return operation(service, {**payload, "workspace": workspace}, actor, agent)
        except model.GateError as error:
            return JSONResponse(error.body(), status_code=error.status)

    @router.post("/branch")
    def branch(request: Request, payload: dict):
        return call(request, payload, ticket_bridge.open_branch)

    @router.post("/answer")
    def answer(request: Request, payload: dict):
        return call(request, payload, ticket_bridge.answer)

    return router
