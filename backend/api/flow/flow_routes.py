"""API engine toků (`backend/flow/`, kontrakt `docs/navrhy/2026-11-03-novy-zaklad.md` §3.1).

Tenký router: validace těla a volání modulu. Data leží v registry.sqlite, každé volání drží `registry_lock`.
Záměr stránky (`docs/navrhy/2026-11-03-platno-2-zamer-stranky.md` §2–§3): `approve` / `reject` jen člověk
(doklad UI, `request.state.actor == "human"`), 409 s `code` (`approval_required`, `not_runnable`, `owner_taken`).
Rozhodnutí schvalovacího uzlu (`node-runs/{id}/decision`) také jen člověk; autor je vždy `human`.
Zápisy podle ID (`versions/{id}/…`, `workflows/{id}/versions|rollback`, `runs/{id}/advance`) projekt v těle nenesou,
proto si routa dohledá projekt workflow a zeptá se zdi brány (`wall.check`) sama: agent bez tokenu v projektu
se zapnutou bránou dostane 403 `gate_required`, srdce projektu projde.
Log pláten 2–4 (`POST /log`, §6) píše člověk, srdce projektu nebo relace brány téhož projektu (`X-Opora-Gate-Token`,
role `worker` / `heart`); jinak 401 `gate_token_invalid` / 403 `gate_scope` jako brána.
Stav záměrů stránek (`page-intents`) a otisk stránky při schválení počítá `backend/flow/page_intents.py` nad přijatým
grafem projektu; graf se čte mimo `registry_lock`.
Plátno toku v knihovně (`library_flow` bez projektu, `docs/navrhy/2026-11-04-knihovna-platna-toku.md` §3) zakládá
`/api/library/flows`; zápisy jeho verzí hlídá místo zdi projektu pravidlo knihovny (`library_routes.writer_refusal`).
Plátno toku se nespouští (`runs` → 409 `not_runnable`).
"""

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.api.brain_opora.writer import heart_project
from backend.api.flow.library_routes import heart_proposal, writer_refusal
from backend.brain_opora.determinism import gate, tokens, wall
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.activity_log import require_human
from backend.canvas.canvas_service import ProjectNotFound
from backend.flow import interpreter, page_intents, workflows, review
from backend.flow.inputs import CandidateIn, CanvasLogIn, RunIn
from backend.flow.canvas_log import log_canvas
from backend.flow.graph_check import FlowInvalid, graph_errors, node_ports
from backend.flow.node_types import catalog
from backend.flow.run_log import read_log
from backend.flow.simulate import simulate
from backend.flow.stalls import list_stalls
from backend.flow.workflows import FlowConflict, FlowNotFound
from backend.project.architecture.work_status import architecture_graph

Kind = Literal["heart", "page_intent", "library_flow"]


class WorkflowIn(BaseModel):
    kind: Kind
    name: str = Field(min_length=1, max_length=200)
    project_id: str | None = Field(default=None, max_length=64)
    owner_ref: str | None = Field(default=None, max_length=200)


class LearnedFrom(BaseModel):
    project: str = Field(min_length=1, max_length=64)
    card: str | None = Field(default=None, max_length=200)
    result: str = Field(min_length=1, max_length=32)


class DraftIn(BaseModel):
    graph: dict[str, Any]
    parent_version_id: str | None = None
    # Metadata verze plátna toku (knihovna §5): poznámka návrhu a odkud se ho agent naučil.
    note: str | None = Field(default=None, max_length=2000)
    learnedFrom: LearnedFrom | None = None


class GraphCheckIn(BaseModel):
    kind: Kind
    graph: Any


class NodePortsIn(BaseModel):
    kind: Kind | None = None
    type: str = Field(min_length=1, max_length=200)
    params: dict[str, Any] = Field(default_factory=dict)
    onError: str | None = Field(default=None, max_length=32)


def _port_json(p):
    return {"name": p.name, "direction": p.direction, "kind": p.kind, "cardinality": p.cardinality,
            "schema": p.schema, "required": p.required, "label": p.label or p.name}


class SimulateIn(BaseModel):
    graph: dict[str, Any]
    caseId: str | None = Field(default=None, max_length=200)
    case: dict[str, Any] | None = None


class RejectIn(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class DecisionIn(BaseModel):
    decision: Literal["approved", "rejected"]


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

    def reviewed(request, operation, identifier, action):
        def locked():
            with service.registry_lock:
                review.check(service.db, operation, identifier, request.query_params.get("expectedReviewDigest"))
                return action(service.db)
        return guarded(locked)

    @router.get("/review")
    def workflow_review(request: Request, project: str, workspace: str, operation: str, identifier: str):
        from backend.api.editor.research_routes import _authorize
        try:
            _authorize(service, request, project, workspace)
            return call(review.observe, operation, identifier, project)
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)

    def walled(request, proposal=False, **ids):
        """Zeď brány pro zápis podle ID: projekt se dohledá z workflow; odmítnutí = odpověď, jinak None.
        Plátno knihovny (bez projektu) hlídá pravidlo části knihovny; `proposal` = draft, který do části člověka
        smí jako návrh i srdce (`heart_proposal`, zapíše se do `request.state.proposed_by`)."""
        if part := call(lambda db: workflows.library_part(db, **ids)):
            if proposal and (proposer := heart_proposal(service, request, part)):
                request.state.proposed_by = proposer
                return None
            return writer_refusal(service, request, part)
        project = call(lambda db: workflows.project_of(db, **ids))
        verdict = wall.check(service, request.method, request.url.path, getattr(request.state, "actor", None),
                             request.headers.get(tokens.HEADER), project, lambda: "")
        return None if verdict.allow else JSONResponse(verdict.body(), status_code=verdict.status)

    def log_author(request, project):
        """Kdo píše do logu pláten: člověk, srdce projektu, nebo relace brány (dělník či srdce) téhož projektu."""
        if getattr(request.state, "actor", None) == "human":
            return "human"
        if heart_project(request) == project:
            return "heart"
        return gate.authenticate(service, request.headers.get(tokens.HEADER), project, ("worker", "heart"))["role"]

    @router.get("/node-types")
    def node_type_list(kind: Kind | None = None):
        """Typy uzlů pro editor podle druhu workflow (`?kind=page_intent` = katalog záměru, `library_flow` = toky dat,
        jinak plátno 1): porty s `kind`, `cardinality`, `required` a `label` (pravidla vazeb, paleta podle portu),
        `params` a `category` uzlu; `dynamicPorts` = porty závisí na `params` (zde výchozí, přesně je spočte
        `graph-check`)."""
        return {"node_types": [
            {"type": t.type, "version": t.version, "trigger": t.trigger, "params": t.params,
             "category": t.category, "dynamicPorts": t.dynamic is not None, "layer": t.layer,
             "use": t.use, "avoid": t.avoid, "intents": list(t.intents),
             "accepts": list(t.accepts), "emits": t.emits or None,
             "ports": [_port_json(p) for p in t.ports]}
            for t in catalog(kind).values()
        ]}

    @router.post("/node-ports")
    def node_port_list(body: NodePortsIn):
        """Porty uzlu pro konkrétní `params` (a `onError: errorOutput` = výstup `error`), aby editor po změně
        parametru překreslil porty dynamického typu (`dynamicPorts`). Neznámý typ = 404."""
        node_type = catalog(body.kind).get(body.type)
        if node_type is None:
            raise HTTPException(404, f"Neznámý typ uzlu {body.type!r}.")
        node = {"params": body.params, "onError": body.onError}
        return {"type": body.type, "ports": [_port_json(p) for p in node_ports(node_type, node, body.kind)]}

    @router.post("/graph-check")
    def graph_check(body: GraphCheckIn):
        """Ověření grafu bez zápisu (`intent propose --dry-run` srdce): `{ok, errors}` podle katalogu druhu."""
        errors = graph_errors(body.graph, catalog(body.kind), body.kind)
        return {"ok": not errors, "errors": errors}

    @router.post("/simulate")
    def simulate_case(body: SimulateIn):
        """Přehraje případ plátna procesu (`docs/navrhy/2026-11-04-platno-procesu.md` §4): čtení, nic nezapíše;
        graf a případ jsou v těle, limity 200 kroků, 20 tabulek × 200 řádků, výraz 500 znaků."""
        return guarded(lambda: simulate(body.graph, body.caseId, body.case))

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
        if body.kind == "library_flow" and body.project_id is None:
            raise HTTPException(422, "Plátno toku v knihovně zakládá POST /api/library/flows {folder, slug, title}.")
        return call(workflows.create_workflow, body.kind, body.name, body.project_id, body.owner_ref)

    @router.get("/workflows/{workflow_id}/versions")
    def version_list(workflow_id: str):
        return {"versions": call(workflows.list_versions, workflow_id)}

    @router.post("/workflows/{workflow_id}/versions")
    def version_draft(workflow_id: str, body: DraftIn, request: Request):
        if refused := walled(request, proposal=True, workflow_id=workflow_id):
            return refused
        meta = {key: value for key, value in (("note", (body.note or "").strip() or None),
                                              ("learnedFrom", body.learnedFrom and body.learnedFrom.model_dump(exclude_none=True)),
                                              ("proposedBy", getattr(request.state, "proposed_by", None))) if value}
        return call(lambda db: workflows.create_draft(db, workflow_id, body.graph, body.parent_version_id,
                                                      meta=meta or None))

    @router.post("/versions/{version_id}/candidate")
    def version_candidate(version_id: str, request: Request, body: CandidateIn | None = None):
        if refused := walled(request, version_id=version_id):
            return refused
        return reviewed(request, "version_candidate", version_id, lambda db: workflows.set_candidate(db, version_id, body.eval_run_id if body else None))

    @router.post("/versions/{version_id}/activate")
    def version_activate(version_id: str, request: Request):
        if refused := walled(request, version_id=version_id):
            return refused
        return reviewed(request, "version_activate", version_id, lambda db: workflows.activate(db, version_id))

    @router.post("/versions/{version_id}/approve")
    def version_approve(version_id: str, request: Request):
        """Schválení kandidáta záměru stránky: jen člověk v UI (token srdce či dělníka dostane 403)."""
        require_human(getattr(request.state, "actor", None), "Záměr stránky schvaluje jen člověk v UI.")
        owner = call(page_intents.owner_of, version_id)
        digest = page_intents.current_digest(accepted_graph(owner[0]), owner[1]) if owner else None
        return reviewed(request, "version_approve", version_id, lambda db: workflows.approve(db, version_id, "human", digest))

    @router.post("/versions/{version_id}/reject")
    def version_reject(version_id: str, body: RejectIn, request: Request):
        require_human(getattr(request.state, "actor", None), "Záměr stránky i návrh plátna toku zamítá jen člověk v UI.")
        return reviewed(request, "version_reject", version_id, lambda db: workflows.reject(db, version_id, body.reason, "human"))

    @router.post("/workflows/{workflow_id}/rollback")
    def version_rollback(workflow_id: str, request: Request):
        if refused := walled(request, workflow_id=workflow_id):
            return refused
        return reviewed(request, "version_rollback", workflow_id, lambda db: workflows.rollback(db, workflow_id))

    @router.post("/versions/{version_id}/runs")
    def run_manual(version_id: str, request: Request, body: RunIn | None = None):
        if refused := walled(request, version_id=version_id):
            return refused
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
    def run_advance(run_id: str, request: Request):
        """Navázání: vypršelé čekání pokračuje větví timeout, přerušený uzel se spustí znovu."""
        if refused := walled(request, run_id=run_id):
            return refused
        return call(interpreter.advance, run_id)

    @router.post("/node-runs/{node_run_id}/decision")
    def approval_decision(node_run_id: str, body: DecisionIn, request: Request):
        require_human(getattr(request.state, "actor", None), "Krok schvaluje jen člověk v UI.")
        return reviewed(request, "approval_decision", node_run_id, lambda db: interpreter.decide(db, node_run_id, body.decision, "human"))

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
