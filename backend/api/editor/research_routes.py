"""Research headers/details for scoped readers; writes only human or heart."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.brain_opora.determinism import brain_files, gate, tokens
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.editor.research import model
from backend.editor.research import service as research


def _authorize(service, request, project, workspace, write=False):
    if request.state.actor == "human":
        return "human", ""
    session = gate.authenticate(service, request.headers.get(tokens.HEADER), project,
                                ("heart",) if write else ("heart", "worker"))
    active = (session["role"] == "heart" and session["workspace_id"] == "main"
              and brain_files.active_workspace(brain_files.brain_dir(service, project)) == workspace)
    if session["workspace_id"] != workspace and not active:
        model.fail("Token belongs to another workspace.", 403, "gate_scope")
    return "agent", session["worker_name"]


def _workspace(service, project, workspace):
    model.identifier(project)
    model.identifier(workspace)
    if workspace == "main":
        return brain_files.active_workspace(brain_files.brain_dir(service, project)) or workspace
    return workspace


def create_research_router(service):
    router = APIRouter(prefix="/api/research", tags=["research"])

    def call(fn):
        try:
            return fn()
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)

    @router.get("")
    def listing(request: Request, project: str, workspace: str, archived: bool = False):
        def run():
            selected = _workspace(service, project, workspace)
            _authorize(service, request, project, selected)
            return {**research.listing(service, project, selected, archived), "workspace": selected}
        return call(run)

    @router.get("/cards/{id}")
    def detail(request: Request, id: str, project: str, workspace: str, revision: int | None = None):
        def run():
            selected = _workspace(service, project, workspace)
            _authorize(service, request, project, selected)
            return {**research.detail(service, project, selected, id, revision), "workspace": selected}
        return call(run)

    @router.get("/edges/{id}")
    def edge_detail(request: Request, id: str, project: str, workspace: str, revision: int | None = None):
        def run():
            selected = _workspace(service, project, workspace)
            _authorize(service, request, project, selected)
            return {**research.edge_detail(service, project, selected, id, revision), "workspace": selected}
        return call(run)

    @router.post("")
    def apply(request: Request, payload: dict):
        def run():
            model.shape(payload, {"project", "workspace", "key", "operations"}, {"continuation", "scopeNodeId"})
            model.identifier(payload["project"]); model.identifier(payload["workspace"])
            selected = _workspace(service, payload["project"], payload["workspace"])
            actor, agent = _authorize(service, request, payload["project"], selected, True)
            result = research.apply(service, {**payload, "workspace": selected}, actor, agent)
            return {**result, "workspace": selected}
        return call(run)

    return router
