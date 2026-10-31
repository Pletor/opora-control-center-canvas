"""Brána mozku (docs/brain-gate.md §4): relace, lístky, odpovědi a schránka.

Druhy požadavků, jejich kontroly a obsluhy drží tabulka `kinds.py`; tady jsou společné kusy pod ní: relace
a jejich ověření, zápis lístku (`record`), odpověď člověka nebo srdce, eskalace srdce a schránka.
Lístek `change` / `ask` pracovníka zapíše i vstup vstupní brány (`intake.py`); srdce budí dál.
Vytvoření i odpověď lístku vydají událost `gate.ticket`. Nic tu nevolá model.
"""
import json
import time
import uuid

from backend.brain_opora.determinism import intake, task_queue, tokens
from backend.brain_opora.determinism.gate_payloads import GateError, answer_payload, session_payload
from backend.canvas.opora_events import emit_event
from database.repositories.gate_tickets import GateTicketStore

INBOX_LIMIT = 100
INTAKE_TEXT = {"change": "proposal", "ask": "question"}  # pole lístku, které jde jako věta do vstupní brány
TOKEN_HINT = "Založte relaci: POST /api/gate/sessions a pošlete token v hlavičce X-Opora-Gate-Token."


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


def _emit(db, project, workspace, ticket, actor, source=None):
    """`from` (role relace, která lístek založila) u vzniku: srdce se nebudí na vlastní eskalaci."""
    data = {"ticketId": ticket["ticketId"], "kind": ticket["kind"], "status": ticket["status"]}
    emit_event(db, project_id=project, workspace_id=workspace, kind="gate.ticket", actor=actor,
               data=data | ({"from": source} if source else {}))


def _intake(db, session, ticket, workspace, answered):
    """Lístek `change` / `ask` pracovníka (ne eskalace srdce) zapíše vstup brány (docs/navrhy/2026-10-30-vstupni-brana.md
    §4). Srdce budí dál i při duplicitě (oprávněné opakování); chyba vstupu lístek nezastaví (`safe_record`)."""
    field = INTAKE_TEXT.get(ticket["kind"])
    body = ticket["body"] if isinstance(ticket["body"], dict) else {}
    if answered or field is None or session.get("role") == "heart" or not isinstance(body.get(field), str):
        return
    intake.safe_record(db, workspace, "gate_" + ticket["kind"], ticket["ticketId"], body[field], ticket["createdAt"])


def record(service, session, kind, body, now=None, *, answered=False, answer=None):
    """Zapíše lístek relace; s `answered` ho rovnou zodpoví brána (`answeredBy = "gate"`, audit synchronních druhů)."""
    project, workspace = session["project_id"], session["workspace_id"]
    ticket_id = "gt_" + uuid.uuid4().hex
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            store = GateTicketStore(db, project)
            store.insert(ticket_id, workspace, session["id"], kind, body, tokens.stamp(now))
            ticket = store.get(ticket_id)
            _intake(db, session, ticket, workspace, answered)
            _emit(db, project, workspace, ticket, _actor(session), session.get("role"))
            if answered:
                store.answer(ticket_id, answer, "gate", tokens.stamp(now))
                ticket = store.get(ticket_id)
                _emit(db, project, workspace, ticket, {"kind": "system", "name": "gate"})
    return ticket


def escalate(service, session, text, now=None):
    """Otázka srdce pro člověka: čekající lístek `ask` `{text, for: "human"}`; srdce se na ni samo nebudí."""
    return record(service, session, "ask", {"text": text, "for": "human"}, now)


def escalations(service, project, workspace, limit=INBOX_LIMIT):
    """`GET /api/brain/heart/escalations`: otevřené otázky srdce pro člověka, od nejnovější."""
    with service.reading(project):
        tickets = GateTicketStore(service.db_for(project), project).escalations(workspace, limit)
    return [{"ticketId": ticket["ticketId"], "text": str(ticket["body"].get("text") or ""),
             "createdAt": ticket["createdAt"]}
            | ({"taskId": ticket["body"]["taskId"]} if isinstance(ticket["body"].get("taskId"), str) else {})
            for ticket in tickets]


REASON_LIMIT = 500


def withdraw(service, session, ticket_id, reason, now=None):
    """Srdce stáhne svou otevřenou eskalaci, kterou fakta už zodpověděla (docs/brain-heart-channel.md §6).

    Lístek se uzavře jako odpověď srdce (`answered`, `answer.withdrawn`), `escalations()` ho už nevypíše; srdce se
    tím nebudí (událost nese `status: answered`). Neznámý 404, cizí lístek 403 `gate_scope`, ne otevřený 409."""
    if not isinstance(reason, str) or not reason.strip() or len(reason) > REASON_LIMIT or "\0" in reason:
        raise GateError(422, "invalid_payload", f"reason je neprázdný text do {REASON_LIMIT} znaků.",
                        'python opora_heart.py escalate --withdraw gt_… --reason "Oprava je sloučená."')
    reason = reason.strip()
    project, workspace = session["project_id"], session["workspace_id"]
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            store = GateTicketStore(db, project)
            ticket = store.get(ticket_id)
            if ticket is None:
                raise GateError(404, "ticket_not_found", "Lístek v projektu neexistuje.",
                                "ID otevřených otázek je ve snímku v sekci OTÁZKY U ČLOVĚKA.")
            if store.heart_escalation_workspace(ticket_id) != workspace:
                raise GateError(403, "gate_scope", "Stáhnout jde jen otázku srdce pro člověka v tomto prostoru.",
                                "ID otevřených otázek je ve snímku v sekci OTÁZKY U ČLOVĚKA.")
            value = {"text": "Staženo srdcem: " + reason, "withdrawn": True, "reason": reason}
            if not store.answer(ticket_id, value, "heart", tokens.stamp(now)):
                raise GateError(409, "ticket_answered", "Otázka už není otevřená.",
                                "Otevřené otázky jsou ve snímku v sekci OTÁZKY U ČLOVĚKA.")
            ticket = store.get(ticket_id)
            _emit(db, project, workspace, ticket, _actor(session))
    return ticket


def heart_escalation_workspace(service, project, ticket_id):
    """Pracovní prostor lístku, když jde o eskalaci srdce pro člověka; jinak None (lístek pracovníka)."""
    with service.reading(project):
        return GateTicketStore(service.db_for(project), project).heart_escalation_workspace(ticket_id)


def answer_text(value):
    """Text odpovědi pro srdce: `{text}` nebo řetězec beze změny, jiná hodnota JSON jako text."""
    if isinstance(value, dict) and isinstance(value.get("text"), str):
        return value["text"]
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


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
    """Odpověď člověka nebo srdce (`answered_by`) na čekající lístek; podruhé 409 `ticket_answered`."""
    actor = task_queue.writer_actor(answered_by)
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
            _emit(db, project, workspace, ticket, actor)
    return ticket


def inbox(service, session, after, wait=0, limit=INBOX_LIMIT, *, interval=0.25, clock=time.monotonic,
          sleep=time.sleep):
    """`{tickets, last}`: zodpovězené lístky relace s `answeredSeq > after`; `last` je nejvyšší vrácené `answeredSeq`.

    S `wait > 0` čeká (long-poll), dokud takový lístek nevznikne nebo neuplyne `wait` sekund.
    """
    project, deadline = session["project_id"], clock() + wait
    while True:
        with service.reading(project):
            tickets = GateTicketStore(service.db_for(project), project).answered_after(session["id"], after, limit)
        if tickets or clock() >= deadline:
            return {"tickets": tickets, "last": tickets[-1]["answeredSeq"] if tickets else after}
        sleep(min(interval, max(deadline - clock(), 0)))
