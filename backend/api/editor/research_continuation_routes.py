"""Scoped original-source reads and durable planning receipt status."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from backend.api.editor.research_routes import _authorize
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.editor.research import continuations, originals, model


def create_research_continuation_router(service):
    router = APIRouter(prefix="/api/research", tags=["research"])

    def call(request, project, workspace, fn, write=False):
        try:
            actor, agent = _authorize(service, request, project, workspace, write)
            return fn(actor, agent)
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)

    @router.get("/continuations")
    def listing(request: Request, project: str, workspace: str):
        return call(request, project, workspace, lambda *_: {
            "project": project, "workspace": workspace, "continuations": continuations.listing(service, project, workspace)})

    @router.get("/originals/{identifier}")
    def original(request: Request, identifier: str, project: str, workspace: str, revision: int | None = None):
        return call(request, project, workspace, lambda *_: originals.read(service, project, workspace, identifier, revision))

    @router.post("/originals/{identifier}/materialize")
    def materialize(request: Request, identifier: str, payload: dict):
        def run(actor, agent):
            model.shape(payload, {"project", "workspace", "revision", "detailsRevision"})
            return originals.materialize(service, payload["project"], payload["workspace"], identifier,
                                         payload["revision"], payload["detailsRevision"], actor, agent)
        return call(request, payload.get("project"), payload.get("workspace"), run, True)

    return router
