"""API engine toků (`backend/flow/`, kontrakt `docs/navrhy/2026-11-03-novy-zaklad.md` §3.1).

Tenký router: validace těla a volání modulu. Data leží v registry.sqlite, každé volání drží `registry_lock`.
Záměr stránky (`docs/navrhy/2026-11-03-platno-2-zamer-stranky.md` §2–§3): `approve` / `reject` jen člověk
(doklad UI, `request.state.actor == "human"`), 409 s `code` (`approval_required`, `not_runnable`, `owner_taken`).
Log pláten 2–4 (`POST /log`, §6) píše člověk, srdce projektu nebo relace brány téhož projektu (`X-Opora-Gate-Token`,
role `worker` / `heart`); jinak 401 `gate_token_invalid` / 403 `gate_scope` jako brána.
Stav záměrů stránek (`page-intents`) a otisk stránky při schválení počítá `backend/flow/page_intents.py` nad přijatým
grafem projektu; graf se čte mimo `registry_lock`.
"""

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.api.brain_opora.writer import heart_project
from backend.brain_opora.determinism import gate, tokens
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.activity_log import require_human
from backend.canvas.canvas_service import ProjectNotFound
from backend.flow import interpreter, page_intents, workflows
from backend.flow.canvas_log import log_canvas
from backend.flow.graph_check import FlowInvalid, graph_errors
from backend.flow.node_types import catalog
from backend.flow.run_log import read_log
from backend.flow.stalls import list_stalls
from backend.flow.workflows import FlowConflict, FlowNotFound
from backend.project.architecture.work_status import architecture_graph

Kind = Literal["heart", "page_intent", "brain_workflow"]


class WorkflowIn(BaseModel):
    kind: Kind
    name: str = Field(min_length=1, max_length=200)
    project_id: str | None = Field(default=None, max_length=64)
    owner_ref: str | None = Field(default=None, max_length=200)


class DraftIn(BaseModel):
    graph: dict[str, Any]
    parent_version_id: str | None = None


class CandidateIn(BaseModel):
    eval_run_id: str | None = None


class GraphCheckIn(BaseModel):
    kind: Kind
    graph: Any


class RunIn(BaseModel):
    payload: Any = None
    node_id: str | None = None


class RejectIn(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class CanvasLogIn(BaseModel):
    project: str = Field(min_length=1, max_length=64)
    canvas: Literal[2, 3, 4]
    kind: str = Field(min_length=3, max_length=64, pattern=r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")
    payload: dict[str, Any] = Field(default_factory=dict)


class DecisionIn(BaseModel):
    decision: Literal["approved", "rejected"]
    actor: str = Field(default="human", min_length=1, max_length=120)


def create_flow_router(service):
    router = APIRouter(prefix="/api/flow", tags=["flow"])

    def guarded(action):
        """404 neznámé ID, 409 nedovolený přechod (s `code` jako `{error, code}`), 422 neplatný graf nebo požadavek."""
        try:
            return action()
        except FlowNotFound as error:
            raise HTTPException(404, str(error)) from error
        except FlowConflict as error:
            if error.code:
                return JSONResponse({"error": str(error), "code": error.code}, status_code=409)
            raise HTTPException(409, str(error)) from error
        except FlowInvalid as error:
            raise HTTPException(422, str(error)) from error

    def call(action, *args):
        def locked():
            with service.registry_lock:
                return action(service.db, *args)
        return guarded(locked)

    def log_author(request, project):
        """Kdo píše do logu pláten: člověk, srdce projektu, nebo relace brány (dělník či srdce) téhož projektu."""
        if getattr(request.state, "actor", None) == "human":
            return "human"
        if heart_project(request) == project:
            return "heart"
        return gate.authenticate(service, request.headers.get(tokens.HEADER), project, ("worker", "heart"))["role"]

    @router.get("/node-types")
    def node_type_list(kind: Kind | None = None):
        """Typy uzlů pro editor podle druhu workflow (`?kind=page_intent` = katalog záměru, jinak plátno 1):
        porty s `kind` a `cardinality` (pravidla vazeb, paleta podle portu) a `params` uzlu."""
        return {"node_types": [
            {"type": t.type, "version": t.version, "trigger": t.trigger, "params": t.params,
             "ports": [{"name": p.name, "direction": p.direction, "kind": p.kind, "cardinality": p.cardinality,
                        "schema": p.schema} for p in t.ports]}
            for t in catalog(kind).values()
        ]}

    @router.post("/graph-check")
    def graph_check(body: GraphCheckIn):
        """Ověření grafu bez zápisu (`intent propose --dry-run` srdce): `{ok, errors}` podle katalogu druhu."""
        errors = graph_errors(body.graph, catalog(body.kind), body.kind)
        return {"ok": not errors, "errors": errors}

    def accepted_graph(project):
        try:
            return architecture_graph(service, project)
        except ProjectNotFound as error:
            raise HTTPException(404, str(error)) from error

    @router.get("/page-intents")
    def page_intent_list(project: str = Query(min_length=1, max_length=64)):
        """Stav záměru každé stránky projektu `[{pageId, state, workflowId?, activeN?, candidateN?, doneCount}]`."""
        graph = accepted_graph(project)
        return {"pages": call(lambda db: page_intents.status(db, project, page_intents.pages_of(graph)))}

    @router.get("/workflows")
    def workflow_list(project: str | None = Query(default=None, max_length=64), kind: Kind | None = None,
                      owner_ref: str | None = Query(default=None, max_length=200)):
        return {"workflows": call(workflows.list_workflows, project, kind, owner_ref)}

    @router.post("/workflows")
    def workflow_create(body: WorkflowIn):
        return call(workflows.create_workflow, body.kind, body.name, body.project_id, body.owner_ref)

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

    @router.post("/versions/{version_id}/approve")
    def version_approve(version_id: str, request: Request):
        """Schválení kandidáta záměru stránky: jen člověk v UI (token srdce či dělníka dostane 403)."""
        require_human(getattr(request.state, "actor", None), "Záměr stránky schvaluje jen člověk v UI.")
        owner = call(page_intents.owner_of, version_id)
        digest = page_intents.current_digest(accepted_graph(owner[0]), owner[1]) if owner else None
        return call(workflows.approve, version_id, "human", digest)

    @router.post("/versions/{version_id}/reject")
    def version_reject(version_id: str, body: RejectIn, request: Request):
        require_human(getattr(request.state, "actor", None), "Záměr stránky zamítá jen člověk v UI.")
        return call(workflows.reject, version_id, body.reason, "human")

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

    @router.post("/log")
    def canvas_log_create(body: CanvasLogIn, request: Request):
        """Vstup logu pláten 2–4 (`backend/flow/canvas_log.py`); chyba `*.failed` probudí srdce."""
        try:
            author = log_author(request, body.project)
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)
        return guarded(lambda: log_canvas(service, body.project, body.canvas, body.kind, body.payload, author))

    @router.get("/stalls")
    def stalls():
        return {"stalls": call(list_stalls)}

    return router
