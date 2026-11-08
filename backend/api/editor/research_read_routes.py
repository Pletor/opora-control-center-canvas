"""Additional scoped reads use exactly the existing research authorization boundary."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.api.editor.research_routes import _authorize, _workspace
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.editor.research import events, reads


def create_research_read_router(service):
    router = APIRouter(prefix="/api/research", tags=["research"])

    def call(request, project, workspace, fn):
        try:
            selected = _workspace(service, project, workspace)
            _authorize(service, request, project, selected)
            return fn(selected)
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)

    @router.get("/topics")
    def topics(request: Request, project: str, workspace: str, archived: bool = False):
        return call(request, project, workspace, lambda selected: reads.topics(service, project, selected, archived))

    @router.get("/cards/{id}/parts")
    def parts(request: Request, id: str, project: str, workspace: str, revision: int | None = None,
              offset: int = 0, size: int = 12000, snapshot: str | None = None):
        return call(request, project, workspace, lambda selected:
                    reads.parts(service, project, selected, id, revision, offset, size, snapshot))

    @router.get("/events")
    def changes(request: Request, project: str, workspace: str, after: int = 0, limit: int = 100):
        return call(request, project, workspace, lambda selected: events.listing(service, project, selected, after, limit))

    return router
