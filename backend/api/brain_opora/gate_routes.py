"""Routy brány mozku (docs/brain-gate.md §4). Logika je v `backend/brain_opora/determinism/gate.py`.

Pracovník se prokazuje hlavičkou `X-Opora-Gate-Token`. Na lístek v H1a odpovídá jen člověk (doklad UI);
token srdce přibude v H2. Každé odmítnutí je JSON s `error`, `code` a `hint`.
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.brain_opora.determinism import gate, tokens
from backend.brain_opora.determinism.gate_payloads import GateError, inbox_query, parse_body

HUMAN_HINT = "Na lístek v tomto kroku odpovídá jen člověk v UI OPORY."


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
    router = APIRouter(prefix="/api/gate")

    def session_of(request):
        return gate.authenticate(service, request.headers.get(tokens.HEADER),
                                 request.query_params.get("project") or None)

    @router.post("/sessions", status_code=201)
    async def open_session(request: Request):
        try:
            payload = parse_body(await request.body())
            return await run_in_threadpool(gate.open_session, service, payload)
        except GateError as error:
            return _refused(error)

    @router.post("/requests", status_code=201)
    async def create_request(request: Request):
        try:
            session = await run_in_threadpool(session_of, request)
            payload = parse_body(await request.body())
            ticket = await run_in_threadpool(gate.create_request, service, session, payload)
        except GateError as error:
            return _refused(error)
        out = {key: ticket[key] for key in ("ticketId", "seq", "kind", "status")}
        return out | ({"answer": ticket["answer"]} if ticket["status"] == "answered" else {})

    @router.get("/inbox")
    async def inbox(request: Request):
        try:
            session = await run_in_threadpool(session_of, request)
            after, wait = inbox_query(request.query_params.get("after"), request.query_params.get("wait"))
        except GateError as error:
            return _refused(error)

        async def fetch():
            return await run_in_threadpool(gate.inbox, service, session, after)

        return await gate.long_poll(fetch, wait)

    @router.get("/tickets/{ticket_id}")
    def ticket(ticket_id: str, request: Request):
        try:
            if request.state.actor == "human" and not request.headers.get(tokens.HEADER):
                return gate.get_ticket(service, _human_project(service, request), ticket_id)
            session = session_of(request)
            return gate.get_ticket(service, session["project_id"], ticket_id, session)
        except GateError as error:
            return _refused(error)

    @router.post("/tickets/{ticket_id}/answer")
    async def answer(ticket_id: str, request: Request):
        try:
            if request.state.actor != "human":
                raise GateError(403, "human_required", "Na lístek smí odpovědět jen člověk.", HUMAN_HINT)
            project = _human_project(service, request)
            payload = parse_body(await request.body())
            return await run_in_threadpool(gate.answer, service, project, ticket_id, payload)
        except GateError as error:
            return _refused(error)

    return router
