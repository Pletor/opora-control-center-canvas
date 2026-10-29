"""Routy brány mozku (docs/brain-gate.md §4, docs/brain-control-api.md §1–§2).

Logika je v `backend/brain_opora/determinism/`: druhy požadavků v `kinds.py`, lístky a schránka v `gate.py`.
Pracovník i srdce se prokazují hlavičkou `X-Opora-Gate-Token`; druhy srdce projdou jen s tokenem srdce.
Na lístek odpovídá člověk (doklad UI) nebo srdce téhož projektu (`answeredBy = "heart"`, docs/brain-heart.md §5).
Každé odmítnutí je JSON s `error`, `code` a `hint`.
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.api.brain_opora import models
from backend.api.brain_opora.writer import heart_project
from backend.brain_opora.determinism import gate, kinds, tokens
from backend.brain_opora.determinism.gate_payloads import GateError, inbox_query, parse_body

HUMAN_HINT = "Na lístek odpovídá jen člověk v UI OPORY nebo srdce projektu."
ROLES = ("worker", "heart")


def _refused(error):
    return JSONResponse(error.body(), status_code=error.status)


def _human_project(service, request):
    """Projekt z `?project=` pro člověka; neexistující projekt je 404 s nápovědou."""
    project = request.query_params.get("project") or ""
    if not service.project_exists(project):
        raise GateError(404, "project_not_found", "Projekt neexistuje nebo chybí ?project=.",
                        "Přidejte ?project=<id projektu>.")
    return project


def create_gate_router(service):
    router = APIRouter(prefix="/api/gate", tags=["gate"])

    def session_of(request, roles=ROLES):
        return gate.authenticate(service, request.headers.get(tokens.HEADER),
                                 request.query_params.get("project") or None, roles)

    @router.post("/sessions", status_code=201, openapi_extra=models.body(models.SessionIn),
                 responses=models.answers(201, models.SessionOut, 404, 413, 422))
    async def open_session(request: Request):
        try:
            payload = parse_body(await request.body())
            return await run_in_threadpool(gate.open_session, service, payload)
        except GateError as error:
            return _refused(error)

    @router.get("/kinds", responses=models.answers(200, models.KindsOut, 401, 403))
    def list_kinds(request: Request):
        """Druhy pro roli volajícího: token pracovníka = druhy pracovníka, token srdce i člověk = všechny.

        Agent bez tokenu vidí druhy pracovníka, aby věděl, co může po založení relace poslat."""
        try:
            if request.headers.get(tokens.HEADER):
                role = session_of(request)["role"]
            else:
                role = "human" if request.state.actor == "human" else "worker"
        except GateError as error:
            return _refused(error)
        return {"role": role, "kinds": kinds.visible(role)}

    @router.post("/requests", status_code=201, openapi_extra=models.body(models.GateRequestIn),
                 responses=models.answers(201, models.GateRequestOut, 401, 403, 404, 409, 413, 422))
    async def create_request(request: Request):
        try:
            session = await run_in_threadpool(session_of, request)
            payload = parse_body(await request.body())
            ticket = await run_in_threadpool(kinds.run, service, session, payload)
        except GateError as error:
            return _refused(error)
        out = {key: ticket[key] for key in ("ticketId", "seq", "kind", "status")}
        return out | ({"answer": ticket["answer"]} if ticket["status"] == "answered" else {})

    @router.get("/inbox", responses=models.answers(200, models.InboxOut, 401, 403, 422))
    async def inbox(request: Request):
        try:
            session = await run_in_threadpool(session_of, request)
            after, wait = inbox_query(request.query_params.get("after"), request.query_params.get("wait"))
        except GateError as error:
            return _refused(error)
        return await run_in_threadpool(gate.inbox, service, session, after, wait)

    @router.get("/tickets/{ticket_id}", responses=models.answers(200, models.Ticket, 401, 403, 404))
    def ticket(ticket_id: str, request: Request):
        try:
            if request.state.actor == "human" and not request.headers.get(tokens.HEADER):
                return gate.get_ticket(service, _human_project(service, request), ticket_id)
            session = session_of(request)
            return gate.get_ticket(service, session["project_id"], ticket_id, session)
        except GateError as error:
            return _refused(error)

    @router.post("/tickets/{ticket_id}/answer", openapi_extra=models.body(models.AnswerIn),
                 responses=models.answers(200, models.Ticket, 403, 404, 409, 422))
    async def answer(ticket_id: str, request: Request):
        try:
            project = request.query_params.get("project") or ""
            heart = bool(project) and heart_project(request) == project
            by = "human" if request.state.actor == "human" else "heart" if heart else None
            if by is None:
                raise GateError(403, "human_required", "Na lístek smí odpovědět jen člověk nebo srdce projektu.",
                                HUMAN_HINT)
            project = _human_project(service, request)
            payload = parse_body(await request.body())
            return await run_in_threadpool(gate.answer, service, project, ticket_id, payload, by)
        except GateError as error:
            return _refused(error)

    return router
