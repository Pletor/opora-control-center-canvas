"""Routy srdce mozku (docs/brain-heart.md §1, §4). Logika je v `backend/brain_opora/heart/`.

- `POST /api/brain/heart/messages {project, workspace, text}`: jen člověk; vstup do supervisoru, budí hned.
- `GET /api/brain/heart/status?project=`: relace, posledních 5 dávek, spánek a nejbližší povolený čas.
- `GET /api/brain/heart/snapshot?project&workspace`: deterministický snímek (čtení je volné).
- `POST /api/brain/heart/escalate {project, workspace, text}`: jen token srdce; lístek `ask` pro člověka
  (`gate.escalate`, stejná funkce jako druh brány `escalate`).
Celá cesta je jen pro loopback (`backend/app/remote_access.py`). Odmítnutí nese `code` a `hint`.
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.api.brain_opora import models
from backend.brain_opora.determinism import gate, gate_setting, snapshot, tokens
from backend.brain_opora.determinism.gate_payloads import GateError, invalid, parse_body
from backend.canvas.activity_log import require_human
from backend.canvas.graph import valid_id

TEXT_LIMIT = 8000
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


def create_heart_router(service, supervisor):
    router = APIRouter(prefix="/api/brain/heart", tags=["heart"])

    @router.post("/messages", openapi_extra=models.body(models.HeartMessageIn),
                 responses=models.answers(200, models.HeartMessageOut, 403, 404, 409, 422))
    async def message(request: Request):
        require_human(request.state.actor, "Srdci píše zprávu jen člověk v UI.")
        try:
            project, workspace, text = _scope(service, parse_body(await request.body()))
            if not await run_in_threadpool(gate_setting.is_on, service, project):
                raise GateError(409, "gate_off", "Srdce pracuje jen v projektu se zapnutou bránou.",
                                'Zapněte bránu: POST /api/brain/gate-setting {"project": "<id>", "enabled": true}.')
        except GateError as error:
            return _refused(error)
        return {"queued": True, "pending": supervisor.message(project, workspace, text)}

    @router.get("/status", responses={404: {"model": models.Refusal}})
    def status(project: str = ""):
        try:
            return supervisor.status(_project(service, project))
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

    return router
