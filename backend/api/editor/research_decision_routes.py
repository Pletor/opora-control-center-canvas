"""Scoped decision review and task projection through the existing research surface."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.api.editor.research_routes import _authorize, _workspace
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.editor.research import decisions, decision_tasks, model


def create_research_decision_router(service):
    router = APIRouter(prefix="/api/research", tags=["research"])

    def call(request, project, workspace, write, fn):
        try:
            selected = _workspace(service, project, workspace)
            actor, name = _authorize(service, request, project, selected, write)
            return fn(selected, actor, name)
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)
        except ValueError as error:
            return JSONResponse({"error": str(error), "code": "research_proposal_invalid"}, status_code=422)

    @router.post("/decision-reviews")
    def review(request: Request, payload: dict):
        def run(workspace, actor, name):
            model.shape(payload, {"project", "workspace", "review"})
            return decisions.review(service, payload["project"], workspace, payload["review"], actor)
        return call(request, payload.get("project"), payload.get("workspace"), True, run)

    @router.get("/decision-reviews")
    def listing(request: Request, project: str, workspace: str, decisionId: str):
        return call(request, project, workspace, False,
                    lambda selected, actor, name: decisions.listing(service, project, selected, decisionId))

    @router.get("/decision-reviews/{id}")
    def read(request: Request, id: str, project: str, workspace: str):
        return call(request, project, workspace, False,
                    lambda selected, actor, name: decisions.read(service, project, selected, id))

    @router.post("/decision-reviews/{id}/tasks")
    def tasks(request: Request, id: str, payload: dict):
        def run(workspace, actor, name):
            model.shape(payload, {"project", "workspace", "tasks"})
            return decision_tasks.materialize(service, payload["project"], workspace, id, payload["tasks"],
                                              {"kind": actor, "name": name or "Člověk"})
        return call(request, payload.get("project"), payload.get("workspace"), True, run)

    @router.get("/decision-reviews/{id}/tasks")
    def task_status(request: Request, id: str, project: str, workspace: str):
        return call(request, project, workspace, False,
                    lambda selected, actor, name: decision_tasks.status(service, project, selected, id))

    @router.post("/decision-reviews/{id}/reconcile")
    def reconcile(request: Request, id: str, payload: dict):
        def run(workspace, actor, name):
            model.shape(payload, {"project", "workspace"})
            return decision_tasks.reconcile(service, payload["project"], workspace, id)
        return call(request, payload.get("project"), payload.get("workspace"), True, run)

    return router
