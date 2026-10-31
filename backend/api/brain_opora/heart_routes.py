"""Routy srdce mozku (docs/brain-heart.md §1, §4). Logika je v `backend/brain_opora/heart/`.

- `POST /api/brain/heart/messages {project, workspace, text}`: člověk, nebo relé záměru (docs/brain-heart-orchestrator.md
  §8): platný token pracovníka brány téhož projektu, zpráva pak nese `via` = jméno relace. Uloží se do
  `brain/messages.jsonl` (snímek ji ukáže v `ZPRÁVY ČLOVĚKA`, §3a), pak jde jako vstup do supervisoru a budí hned.
- `GET /api/brain/heart/status?project=`: relace, posledních 5 dávek, spánek, nejbližší povolený čas a `current`
  (běžící dávka `{startedAt, inputs}`, jinak `null`).
- `GET /api/brain/heart/escalations?project&workspace`: jen člověk; otevřené otázky srdce pro člověka, od nejnovější
  (docs/brain-heart-channel.md §2). Odpověď jde přes `POST /api/gate/tickets/{id}/answer` a srdce budí.
- `GET /api/brain/heart/snapshot?project&workspace`: deterministický snímek (čtení je volné).
- `GET /api/brain/heart/context?project&workspace&name`: jen token srdce svého projektu a prostoru; data dílny
  `{name, items}` pro `ctx <name>` (`determinism/workshop.py`, §3b). Pracovník ani člověk je nečtou. `name=plan-of`
  s `&of=<projekt>[&ofWorkspace=<prostor>][&ofNode=<uzel>]` vrátí plán jiného projektu zhuštěně, s `ofNode` plné
  zadání podstromu uzlu (docs/brain-heart-orchestrator.md §9 O7).
- `POST /api/brain/heart/escalate {project, workspace, text}`: jen token srdce; lístek `ask` pro člověka
  (`gate.escalate`, stejná funkce jako druh brány `escalate`).
- `POST /api/brain/heart/intake {project, workspace, entry, verdict, reason?, requirement?, title?, openCondition?}`:
  jen token srdce; potvrdí nebo opraví stanovisko vstupu vstupní brány svého prostoru (vrstva `heart`,
  `intake.confirm`, docs/navrhy/2026-10-30-vstupni-brana.md) a případně vstup naváže na požadavek
  (`requirement` = `new` s `title`, nebo `rq_…`; docs/navrhy/2026-10-30-metriky-a-spoustece.md §5).
- `POST /api/brain/heart/milestone {project, workspace, area, title, criteria}`: jen token srdce; návrh milníku oblasti
  (`proposed`, `milestones.propose`). Aktivuje ho člověk, nebo srdce při plné autonomii (`POST /api/intake/milestone`, `require_authority`).
- `POST /api/brain/heart/brief {project, workspace, requirement, synthesis}`: jen token srdce; uloží syntézu výslechu
  požadavku a vrátí `{requirement, status, missing}`; `clear` jen bez `missing` (`brief.save_synthesis`,
  docs/navrhy/2026-10-30-vyslech-srdce.md §7).
- `POST /api/brain/heart/ask {project, workspace, requirement, question, recommended, why}`: jen token srdce; otázka
  výslechu pro člověka, nejvýš 3 otevřené a 3 kola (`brief.ask`).
- `POST /api/brain/heart/brief/research {project, workspace, requirement, costUsd?, fragmentId?, digest?, sources?}`:
  jen token srdce; strop rešerše požadavku (§8). Bez `costUsd` kontrola před `research --requirement` (vyčerpáno =
  409 `brief_research_spent`), s `costUsd` přičtení ceny do `intake_briefs.cost_usd` (`brief.research_budget` /
  `brief.research_spend`).
Celá cesta je jen pro loopback (`backend/app/remote_access.py`). Odmítnutí nese `code` a `hint`.
"""
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.api.brain_opora import models
from backend.brain_opora.determinism import (
    brief,
    gate,
    gate_setting,
    intake,
    milestones,
    snapshot,
    tokens,
    workshop,
)
from backend.brain_opora.determinism.gate_payloads import GateError, invalid, parse_body
from backend.canvas.activity_log import require_human
from backend.canvas.graph import valid_id

TEXT_LIMIT = 8000
INTAKE_KEYS = {"project", "workspace", "entry", "verdict", "reason", "requirement", "title", "openCondition"}
MILESTONE_KEYS = {"project", "workspace", "area", "title", "criteria"}
BRIEF_KEYS = {"project", "workspace", "requirement", "synthesis"}
ASK_KEYS = {"project", "workspace", "requirement", "question", "recommended", "why"}
RESEARCH_KEYS = {"project", "workspace", "requirement"}
RESEARCH_EXTRA = {"costUsd", "fragmentId", "digest", "sources"}
EXAMPLE = '{"project": "<id>", "workspace": "main", "text": "Chci web o dvou stránkách: …"}'


def _refused(error):
    return JSONResponse(error.body(), status_code=error.status)


def _scope(service, payload):
    """`{project, workspace, text}` → `(project, workspace, text)`; neznámý projekt 404."""
    if not isinstance(payload, dict) or set(payload) != {"project", "workspace", "text"}:
        raise invalid("Tělo je přesně {project, workspace, text}.", "Příklad: " + EXAMPLE)
    project, workspace, text = payload["project"], payload["workspace"], payload["text"]
    if not isinstance(project, str) or not (project == "draft" or valid_id(project)) or not valid_id(workspace):
        raise invalid("Neplatné ID projektu nebo pracovního prostoru.", "Příklad: " + EXAMPLE)
    if not isinstance(text, str) or not text.strip() or len(text) > TEXT_LIMIT or "\0" in text:
        raise invalid(f"text je neprázdný text do {TEXT_LIMIT} znaků.", "Příklad: " + EXAMPLE)
    if not service.project_exists(project):
        raise GateError(404, "project_not_found", "Projekt neexistuje.", "ID projektu najdete v GET /api/bootstrap.")
    return project, workspace, text.strip()


def _project(service, project):
    if not service.project_exists(project):
        raise GateError(404, "project_not_found", "Projekt neexistuje nebo chybí ?project=.",
                        "Přidejte ?project=<id projektu>.")
    return project


async def _heart_session(service, request, payload):
    """Relace srdce pro tělo `{project, workspace, …}`: jen token srdce téhož projektu a prostoru."""
    if not isinstance(payload["project"], str) or not isinstance(payload["workspace"], str):
        raise invalid("project a workspace jsou text.", "Použijte OPORA_PROJECT a OPORA_WORKSPACE z prostředí.")
    project = _project(service, payload["project"])
    session = await run_in_threadpool(gate.authenticate, service, request.headers.get(tokens.HEADER), project,
                                      ("heart",))
    if session["workspace_id"] != payload["workspace"]:
        raise GateError(403, "gate_scope", "Token srdce platí jen pro svůj pracovní prostor.",
                        "Použijte OPORA_WORKSPACE z prostředí dávky.")
    return session


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def create_heart_router(service, supervisor):
    router = APIRouter(prefix="/api/brain/heart", tags=["heart"])

    @router.post("/messages", openapi_extra=models.body(models.HeartMessageIn),
                 responses=models.answers(200, models.HeartMessageOut, 401, 403, 404, 409, 422))
    async def message(request: Request):
        header = request.headers.get(tokens.HEADER)
        human = request.state.actor == "human"
        if not human and not header:
            require_human(request.state.actor, "Srdci píše zprávu člověk v UI, nebo relé s tokenem pracovníka brány.")
        via = None
        try:
            project, workspace, text = _scope(service, parse_body(await request.body()))
            if not human:
                session = await run_in_threadpool(gate.authenticate, service, header, project, ("worker",))
                via = session["worker_name"]
            if not await run_in_threadpool(gate_setting.is_on, service, project):
                raise GateError(409, "gate_off", "Srdce pracuje jen v projektu se zapnutou bránou.",
                                'Zapněte bránu: POST /api/brain/gate-setting {"project": "<id>", "enabled": true}.')
        except GateError as error:
            return _refused(error)
        pending = await run_in_threadpool(supervisor.message, project, workspace, text, None, via)
        return {"queued": True, "pending": pending}

    @router.get("/status", responses={404: {"model": models.Refusal}})
    def status(project: str = ""):
        try:
            return supervisor.status(_project(service, project))
        except GateError as error:
            return _refused(error)

    @router.get("/escalations", responses=models.answers(200, models.EscalationsOut, 403, 404, 422))
    def escalations(request: Request, project: str = "", workspace: str = ""):
        require_human(request.state.actor, "Otázky srdce čte jen člověk v UI.")
        try:
            if not valid_id(workspace):
                raise invalid("Chybí ?workspace=.", "Přidejte ?project=<id>&workspace=<main | draft | id>.")
            return {"escalations": gate.escalations(service, _project(service, project), workspace)}
        except GateError as error:
            return _refused(error)

    @router.get("/snapshot", responses=models.answers(200, models.SnapshotOut, 404, 422))
    def read_snapshot(project: str = "", workspace: str = ""):
        try:
            if not valid_id(workspace):
                raise invalid("Chybí ?workspace=.", "Přidejte ?project=<id>&workspace=<main | draft | id>.")
            return {"snapshot": snapshot.snapshot(service, _project(service, project), workspace)}
        except GateError as error:
            return _refused(error)

    @router.get("/context", responses=models.answers(200, models.ContextOut, 401, 403, 404, 422))
    def context(request: Request, project: str = "", workspace: str = "", name: str = "", of: str = "",
                ofWorkspace: str = "", ofNode: str = ""):
        try:
            if not valid_id(workspace):
                raise invalid("Chybí ?workspace=.", "Přidejte ?project=<id>&workspace=<main | draft | id>&name=tasks.")
            if ((of and of != "draft" and not valid_id(of)) or (ofWorkspace and not valid_id(ofWorkspace))
                    or (ofNode and not valid_id(ofNode))):
                raise invalid("Neplatné ID projektu, prostoru nebo uzlu plánu.",
                              "&of=<id projektu>[&ofWorkspace=<id>][&ofNode=<id uzlu>].")
            session = gate.authenticate(service, request.headers.get(tokens.HEADER), _project(service, project),
                                        ("heart",))
            if session["workspace_id"] != workspace:
                raise GateError(403, "gate_scope", "Token srdce platí jen pro svůj pracovní prostor.",
                                "Použijte OPORA_WORKSPACE z prostředí dávky.")
            return {"name": name, "items": workshop.context(service, project, workspace, name, of, ofWorkspace,
                                                                  ofNode)}
        except GateError as error:
            return _refused(error)

    @router.post("/escalate", status_code=201, openapi_extra=models.body(models.HeartMessageIn),
                 responses=models.answers(201, models.EscalateOut, 401, 403, 404, 422))
    async def escalate(request: Request):
        try:
            project, workspace, text = _scope(service, parse_body(await request.body()))
            session = await run_in_threadpool(gate.authenticate, service, request.headers.get(tokens.HEADER),
                                              project, ("heart",))
            if session["workspace_id"] != workspace:
                raise GateError(403, "gate_scope", "Token srdce platí jen pro svůj pracovní prostor.",
                                "Použijte OPORA_WORKSPACE z prostředí dávky.")
            ticket = await run_in_threadpool(gate.escalate, service, session, text)
        except GateError as error:
            return _refused(error)
        return {"ticketId": ticket["ticketId"], "kind": ticket["kind"], "status": ticket["status"]}

    @router.post("/intake", openapi_extra=models.body(models.IntakeVerdictIn),
                 responses=models.answers(200, models.IntakeVerdictOut, 401, 403, 404, 422))
    async def intake_verdict(request: Request):
        try:
            payload = parse_body(await request.body())
            keys = set(payload) if isinstance(payload, dict) else set()
            if not {"project", "workspace", "entry", "verdict"} <= keys <= INTAKE_KEYS:
                raise invalid("Tělo je {project, workspace, entry, verdict, reason?, requirement?, title?, openCondition?}.",
                              "python opora_heart.py intake --entry ie_… --verdict later_extension --reason \"…\"")
            session = await _heart_session(service, request, payload)
            return await run_in_threadpool(intake.confirm, service, session, payload["entry"], payload["verdict"],
                                           payload.get("reason", ""), payload.get("requirement"),
                                           payload.get("title"), payload.get("openCondition"))
        except GateError as error:
            return _refused(error)

    @router.post("/milestone", status_code=201, openapi_extra=models.body(models.MilestoneProposalIn),
                 responses=models.answers(201, models.MilestoneProposalOut, 401, 403, 404, 422))
    async def propose_milestone(request: Request):
        try:
            payload = parse_body(await request.body())
            if not isinstance(payload, dict) or set(payload) != MILESTONE_KEYS:
                raise invalid("Tělo je přesně {project, workspace, area, title, criteria}.", milestones.HINT)
            session = await _heart_session(service, request, payload)
            return await run_in_threadpool(milestones.propose, service, session, payload["area"], payload["title"],
                                           payload["criteria"], _now())
        except GateError as error:
            return _refused(error)

    @router.post("/brief", openapi_extra=models.body(models.BriefSynthesisIn),
                 responses=models.answers(200, models.BriefSynthesisOut, 401, 403, 404, 422))
    async def brief_synthesis(request: Request):
        try:
            payload = parse_body(await request.body())
            if not isinstance(payload, dict) or set(payload) != BRIEF_KEYS:
                raise invalid("Tělo je přesně {project, workspace, requirement, synthesis}.", brief.HINT)
            session = await _heart_session(service, request, payload)
            return await run_in_threadpool(brief.save_synthesis, service, session, payload["requirement"],
                                           payload["synthesis"], _now())
        except GateError as error:
            return _refused(error)

    @router.post("/ask", status_code=201, openapi_extra=models.body(models.BriefAskIn),
                 responses=models.answers(201, models.BriefAskOut, 401, 403, 404, 409, 422))
    async def brief_ask(request: Request):
        try:
            payload = parse_body(await request.body())
            if not isinstance(payload, dict) or set(payload) != ASK_KEYS:
                raise invalid("Tělo je přesně {project, workspace, requirement, question, recommended, why}.",
                              brief.ASK_HINT)
            session = await _heart_session(service, request, payload)
            return await run_in_threadpool(brief.ask, service, session, payload["requirement"], payload["question"],
                                           payload["recommended"], payload["why"], _now())
        except GateError as error:
            return _refused(error)

    @router.post("/brief/research", openapi_extra=models.body(models.BriefResearchIn),
                 responses=models.answers(200, models.BriefResearchOut, 401, 403, 404, 409, 422))
    async def brief_research(request: Request):
        try:
            payload = parse_body(await request.body())
            if not isinstance(payload, dict) or not RESEARCH_KEYS <= set(payload) <= RESEARCH_KEYS | RESEARCH_EXTRA:
                raise invalid("Tělo je {project, workspace, requirement, costUsd?, fragmentId?, digest?, sources?}.",
                              "python opora_heart.py research --requirement rq_… --question Q --title T")
            if "costUsd" not in payload and set(payload) - RESEARCH_KEYS:
                raise invalid("fragmentId, digest a sources jdou jen s costUsd.", "Bez costUsd je to kontrola stropu.")
            session = await _heart_session(service, request, payload)
            if "costUsd" not in payload:
                return await run_in_threadpool(brief.research_budget, service, session, payload["requirement"])
            return await run_in_threadpool(brief.research_spend, service, session, payload["requirement"],
                                           payload["costUsd"], payload.get("fragmentId"), payload.get("digest") or "",
                                           payload.get("sources") or [], _now())
        except GateError as error:
            return _refused(error)

    return router
