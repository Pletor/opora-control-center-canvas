"""Scope-bound readback of immutable Desktop preparations for explicit human review."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.api.editor.research_routes import _authorize
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.editor.agent_memory.desktop_review import apply, read
from backend.editor.research.model import identifier as valid_identifier


def create_desktop_review_router(service):
    router = APIRouter(prefix='/api/desktop-reviews', tags=['desktop-review'])
    def call(request, project, workspace, write, callback):
        try:
            valid_identifier(project); valid_identifier(workspace)
            selected = workspace
            actor, _ = _authorize(service, request, project, selected, write)
            return callback(selected, actor)
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)

    @router.get('/{identifier}')
    def review(identifier: str, request: Request, project: str, workspace: str):
        return call(request, project, workspace, False, lambda selected, actor: read(service, project, selected, identifier))

    @router.post('/{identifier}/apply')
    def decide(identifier: str, request: Request, payload: dict):
        if set(payload) != {'project', 'workspace', 'digest'}:
            raise ValueError('Expected project, workspace and immutable review digest.')
        return call(request, payload['project'], payload['workspace'], True,
                    lambda selected, actor: apply(service, payload['project'], selected, identifier, payload['digest'], actor))
    return router
