"""API engine toků (`backend/flow/`, kontrakt `docs/navrhy/2026-11-03-novy-zaklad.md` §3.1).

Tenký router: validace těla a volání modulu. Data leží v registry.sqlite, každé volání drží `registry_lock`.
"""

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.flow import interpreter, workflows
from backend.flow.graph_check import FlowInvalid
from backend.flow.run_log import read_log
from backend.flow.stalls import list_stalls
from backend.flow.workflows import FlowConflict, FlowNotFound


class WorkflowIn(BaseModel):
    kind: Literal["heart", "page_intent", "brain_workflow"]
    name: str = Field(min_length=1, max_length=200)
    project_id: str | None = Field(default=None, max_length=64)


class DraftIn(BaseModel):
    graph: dict[str, Any]
    parent_version_id: str | None = None


class CandidateIn(BaseModel):
    eval_run_id: str | None = None


class RunIn(BaseModel):
    payload: Any = None
    node_id: str | None = None


class DecisionIn(BaseModel):
    decision: Literal["approved", "rejected"]
    actor: str = Field(default="human", min_length=1, max_length=120)


def create_flow_router(service):
    router = APIRouter(prefix="/api/flow", tags=["flow"])

    def call(action, *args):
        """404 neznámé ID, 409 nedovolený přechod, 422 neplatný graf nebo požadavek."""
        try:
            with service.registry_lock:
                return action(service.db, *args)
        except FlowNotFound as error:
            raise HTTPException(404, str(error)) from error
        except FlowConflict as error:
            raise HTTPException(409, str(error)) from error
        except FlowInvalid as error:
            raise HTTPException(422, str(error)) from error

    @router.get("/workflows")
    def workflow_list(project: str | None = Query(default=None, max_length=64)):
        return {"workflows": call(workflows.list_workflows, project)}

    @router.post("/workflows")
    def workflow_create(body: WorkflowIn):
        return call(workflows.create_workflow, body.kind, body.name, body.project_id)

    @router.get("/workflows/{workflow_id}/versions")
    def version_list(workflow_id: str):
        return {"versions": call(workflows.list_versions, workflow_id)}

    @router.post("/workflows/{workflow_id}/versions")
    def version_draft(workflow_id: str, body: DraftIn):
        return call(workflows.create_draft, workflow_id, body.graph, body.parent_version_id)

    @router.post("/versions/{version_id}/candidate")
    def version_candidate(version_id: str, body: CandidateIn | None = None):
        return call(workflows.set_candidate, version_id, body.eval_run_id if body else None)

    @router.post("/versions/{version_id}/activate")
    def version_activate(version_id: str):
        return call(workflows.activate, version_id)

    @router.post("/workflows/{workflow_id}/rollback")
    def version_rollback(workflow_id: str):
        return call(workflows.rollback, workflow_id)

    @router.post("/versions/{version_id}/runs")
    def run_manual(version_id: str, body: RunIn | None = None):
        body = body or RunIn()
        trigger = {"source": "manual", "payload": body.payload, "node_id": body.node_id}
        return call(interpreter.start_run, version_id, trigger)

    @router.get("/runs")
    def run_list(workflow: str | None = None, limit: int = Query(default=100, ge=1, le=500)):
        return {"runs": call(interpreter.list_runs, workflow, limit)}

    @router.get("/runs/{run_id}")
    def run_detail(run_id: str):
        return call(interpreter.get_run, run_id)

    @router.get("/runs/{run_id}/log")
    def run_log(run_id: str, seq: int = Query(default=0, ge=0), limit: int = Query(default=500, ge=1, le=2000)):
        call(interpreter.get_run, run_id)
        return {"events": call(read_log, run_id, seq, limit)}

    @router.post("/runs/{run_id}/advance")
    def run_advance(run_id: str):
        """Navázání: vypršelé čekání pokračuje větví timeout, přerušený uzel se spustí znovu."""
        return call(interpreter.advance, run_id)

    @router.post("/node-runs/{node_run_id}/decision")
    def approval_decision(node_run_id: str, body: DecisionIn):
        return call(interpreter.decide, node_run_id, body.decision, body.actor)

    @router.get("/stalls")
    def stalls():
        return {"stalls": call(list_stalls)}

    return router
