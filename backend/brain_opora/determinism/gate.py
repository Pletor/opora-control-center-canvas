"""Brána mozku (docs/brain-gate.md §4): relace pracovníků, lístky, odpovědi a schránka.

Pracovník (např. z agent-office) pošle požadavek a odpověď mu přijde do schránky. Registr `HANDLERS`
drží deterministické obsluhy podle druhu: ta odpoví hned v tomtéž požadavku. `ask` a `change` obsluhu
nemají a čekají, až odpoví člověk (v H2 i srdce). `next` a `report` obsluhuje fronta úkolů (`task_queue`, H1b).
Vytvoření i odpověď lístku vydají událost `gate.ticket`. Nic tu nevolá model.
"""
import asyncio
import time
import uuid

from backend.brain_opora.determinism import task_queue, tokens
from backend.brain_opora.determinism.gate_payloads import (
    GateError,
    answer_payload,
    request_payload,
    session_payload,
)
from backend.canvas.opora_events import emit_event
from database.repositories.gate_tickets import GateTicketStore

INBOX_LIMIT = 100
TOKEN_HINT = "Založte relaci: POST /api/gate/sessions a pošlete token v hlavičce X-Opora-Gate-Token."


# Obsluha je `handler(service, session, body, now) -> odpověď`; odmítnutí hlásí `GateError` (lístek pak nevznikne).
HANDLERS = {"next": task_queue.next_task, "report": task_queue.report}


def register(kind, handler):
    """Nahradí obsluhu druhu (např. v testu nebo pro další deterministický druh)."""
    HANDLERS[kind] = handler


def _workspace_known(service, project, workspace):
    if workspace in ("draft", "main"):
        return True
    return any(row["id"] == workspace for row in service.workspaces(project))


def open_session(service, payload):
    """`POST /api/gate/sessions` → `{sessionId, token, expiresAt}`."""
    project, workspace, worker = session_payload(payload)
    if not service.project_exists(project):
        raise GateError(404, "project_not_found", "Projekt neexistuje.", "ID projektu najdete v GET /api/bootstrap.")
    if not _workspace_known(service, project, workspace):
        raise GateError(404, "workspace_not_found", "Pracovní prostor v projektu neexistuje.",
                        "Použijte main, draft nebo ID pracovního prostoru projektu.")
    return tokens.issue_worker(service, project, workspace, worker)


def authenticate(service, token, project=None, roles=("worker",)):
    """Platná relace tokenu; jinak 401 `gate_token_invalid`, cizí projekt nebo role 403 `gate_scope`."""
    session = tokens.verify(service, token) if token else None
    if session is None:
        raise GateError(401, "gate_token_invalid", "Token brány chybí, je neznámý, prošlý nebo zneplatněný.",
                        TOKEN_HINT)
    if (project and project != session["project_id"]) or session["role"] not in roles:
        raise GateError(403, "gate_scope", "Token brány platí jen pro svůj projekt a pracovní prostor.",
                        "Pro jiný projekt založte novou relaci: POST /api/gate/sessions.")
    return session


def _actor(session):
    return {"kind": "agent", "name": session["worker_name"]} if session else {"kind": "human", "name": None}


def _emit(db, project, workspace, ticket, actor):
    emit_event(db, project_id=project, workspace_id=workspace, kind="gate.ticket", actor=actor,
               data={"ticketId": ticket["ticketId"], "kind": ticket["kind"], "status": ticket["status"]})


def create_request(service, session, payload, now=None):
    """`POST /api/gate/requests` → lístek; s deterministickou obsluhou už zodpovězený."""
    kind, body = request_payload(payload)
    project, workspace = session["project_id"], session["workspace_id"]
    ticket_id = "gt_" + uuid.uuid4().hex
    handler = HANDLERS.get(kind)
    # Obsluha běží dřív než zápis lístku a se svými zámky: odmítnutý požadavek lístek nezaloží a přehled
    # karet pro prázdnou frontu (zámek grafu, pak projektu) se nečte pod zámkem projektu.
    result = handler(service, session, body, now) if handler is not None else None
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            store = GateTicketStore(db, project)
            store.insert(ticket_id, workspace, session["id"], kind, body, tokens.stamp(now))
            ticket = store.get(ticket_id)
            _emit(db, project, workspace, ticket, _actor(session))
            if handler is not None:
                store.answer(ticket_id, result, "gate", tokens.stamp(now))
                ticket = store.get(ticket_id)
                _emit(db, project, workspace, ticket, {"kind": "system", "name": "gate"})
    return ticket


def get_ticket(service, project, ticket_id, session=None):
    """Lístek projektu; s relací pracovníka jen jeho vlastní (cizí = 403 `gate_scope`)."""
    with service.reading(project):
        ticket = GateTicketStore(service.db_for(project), project).get(ticket_id)
    if ticket is None:
        raise GateError(404, "ticket_not_found", "Lístek v projektu neexistuje.",
                        "ticketId vrací POST /api/gate/requests.")
    if session is not None and ticket["sessionId"] != session["id"]:
        raise GateError(403, "gate_scope", "Lístek patří jiné relaci.", "Čtěte jen své lístky nebo GET /api/gate/inbox.")
    return ticket


def answer(service, project, ticket_id, payload, answered_by="human", now=None):
    """Odpověď člověka na čekající lístek; podruhé 409 `ticket_answered`."""
    value = answer_payload(payload)
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            store = GateTicketStore(db, project)
            ticket = store.get(ticket_id)
            if ticket is None:
                raise GateError(404, "ticket_not_found", "Lístek v projektu neexistuje.",
                                "ID lístku najdete v události gate.ticket.")
            if not store.answer(ticket_id, value, answered_by, tokens.stamp(now)):
                raise GateError(409, "ticket_answered", "Lístek už má odpověď.", "Načtěte ho: GET /api/gate/tickets/{id}.")
            ticket = store.get(ticket_id)
            workspace = db.execute("SELECT workspace_id FROM gate_tickets WHERE id=?", (ticket_id,)).fetchone()[0]
            _emit(db, project, workspace, ticket, {"kind": "human", "name": None})
    return ticket


def inbox(service, session, after, limit=INBOX_LIMIT):
    """`{tickets, last}`: zodpovězené lístky relace s `answeredSeq > after`; `last` je nejvyšší vrácené `answeredSeq`."""
    project = session["project_id"]
    with service.reading(project):
        tickets = GateTicketStore(service.db_for(project), project).answered_after(session["id"], after, limit)
    return {"tickets": tickets, "last": tickets[-1]["answeredSeq"] if tickets else after}


async def long_poll(fetch, wait, *, interval=0.25, clock=time.monotonic, sleep=asyncio.sleep):
    """Volá `fetch()` (async), dokud nevrátí neprázdné `tickets` nebo neuplyne `wait` sekund."""
    deadline = clock() + wait
    result = await fetch()
    while not result["tickets"] and clock() < deadline:
        await sleep(min(interval, max(deadline - clock(), 0)))
        result = await fetch()
    return result
