"""Ticket jako jednotka práce v bráně (docs/navrhy/2026-11-03-novy-zaklad.md §3.3): obsluhy druhů `ticket.*`.

Srdce ticket vydá (`ticket.issue` → `issued`) a odpovídá na zpětnou vazbu (`ticket.answer` s `feedbackId`).
Dělník (orchestrátor kanceláře) si řekne o práci (`ticket.request`: držený ticket znovu, jinak nejstarší vydaný),
vezme ji (`ticket.claim` → `claimed`), hlásí zpětnou vazbu (`ticket.feedback`; první položka posune `claimed` na
`in_progress`, otázka na `needs_answer`) a odevzdá (`ticket.deliver` → `delivered`). Poslední odpověď na otázku
vrátí `needs_answer` do `in_progress`. Přechody hlídá `ticket_model.advance`; audit každého požadavku zapíše brána
do `gate_tickets` (událost `gate.ticket`). Nic tu nevolá model.
`ticket.claim` s `executionId` naváže ticket na běžící exekuci karty (`ticket_lifecycle.bind`); odevzdaný ticket pak
posouvají fakta exekuce (`ticket_lifecycle.follow`: ověřeno, sloučeno, zrušeno). `ticket.release` vrátí vzatý ticket
(`claimed` → `issued`), když kancelář nedostala místo ani exekuci.
Převzetí: `ticket.claim` jiné relace téhož prostoru na držený ticket projde, když nese `executionId` exekuce ticketu
(tatáž exekuce po restartu kanceláře) nebo když relace držitele vypršela, je zneplatněná či neexistuje. Stav se
nemění, ticket drží nová relace a vznikne událost `ticket.resumed` `{ticketId, fromSession, toSession}`.
"""
import uuid

from backend.agi_pletor.linie import work as linie_work
from backend.brain import pins
from backend.brain_opora.determinism import gate, ticket_lifecycle, tokens
from backend.brain_opora.determinism.gate_payloads import GateError, shaped
from backend.brain_opora.determinism.ticket_model import (
    LIST_LIMIT,
    STATES,
    TEXT_LIMIT,
    advance,
    claim_payload,
    deliver_payload,
    feedback_payload,
    issue_payload,
    neighbors,
    ticket_id,
)
from backend.canvas.opora_events import emit_event
from backend.flow.graph_check import FlowInvalid
from backend.flow.page_intents import intent_claims
from backend.flow.workflows import FlowNotFound
from backend.project.site_admin.summary import design_ref
from database.repositories.gate_sessions import GateSessionStore
from database.repositories.tickets import HELD, TicketStore

MISSING_HINT = "ID ticketu vrací ticket.request nebo GET /api/brain/tickets."
HELD_HINT = "Pracujte jen s ticketem, který jste vzali přes ticket.claim; svůj vrátí ticket.request."


def for_worker(ticket):
    """Ticket pro dělníka: tělo bez ID, strojová vrstva vedle a zpětná vazba s odpověďmi srdce."""
    return {"ticketId": ticket["ticketId"], "status": ticket["status"], "body": ticket["body"],
            "machine": ticket["machine"],
            "feedback": [{key: item[key] for key in ("feedbackId", "kind", "text", "answer")}
                         for item in ticket["feedback"]]}


def _found(store, session, ticket_id_):
    ticket = store.get(ticket_id_)
    if ticket is None:
        raise GateError(404, "ticket_not_found", "Ticket v projektu neexistuje.", MISSING_HINT)
    # Srdce vydává tickety i do prostorů karet (git projekt), takže na ně odpovídá a ruší je v celém projektu.
    if ticket["workspaceId"] != session["workspace_id"] and session.get("role") != "heart":
        raise GateError(403, "gate_scope", "Ticket patří jinému pracovnímu prostoru.", MISSING_HINT)
    return ticket


def _held(store, session, ticket_id_):
    ticket = _found(store, session, ticket_id_)
    if ticket["sessionId"] != session["id"]:
        raise GateError(409, "ticket_not_held", "Ticket nedrží tato relace.", HELD_HINT)
    return ticket


def _walk(store, ticket, targets, at, **fields):
    """Projde přechody `targets` po jednom (každý přes `advance`) a zapíše výsledný stav compare-and-set."""
    status = ticket["status"]
    for target in targets:
        status = advance(status, target)
    if status != ticket["status"] and not store.move(ticket["ticketId"], ticket["status"], status, at, **fields):
        raise GateError(409, "ticket_state", "Ticket mezitím změnil stav.", "Načtěte ho znovu přes ticket.request.")
    return status


def _write(service, session, work):
    project = session["project_id"]
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            return work(TicketStore(db, project))


def issue(service, session, body, now=None):
    """`ticket.issue` (jen srdce): nový ticket ve stavu `issued` v prostoru karty (`workspace`, git projekt má
    karty v prostoru domény), jinak v prostoru tokenu srdce. S `cardId` doplní do strojové vrstvy následníky
    a předchůdce karty z grafu toho prostoru (`ticket_model.neighbors`); karta pod webovou doménou projektu s design
    systémem dostane `design = {revision, export}` (`site_admin.summary.design_ref`). Piny Brainu přeloží `pins.for_ticket`
    (neznámé ID 422). S `intent` ověří, že verze je aktivní záměr stránky projektu a uzly jsou `intent.done`, a jejich
    `claim` doplní na konec `doneCriteria` (kritérium je fakt z grafu, srdce ho do těla nepíše)."""
    worker_body, machine = issue_payload(body)
    machine["pins"] = _pins(service, machine["pins"])
    if "intent" in machine:
        claims = _claims(service, session["project_id"], machine["intent"])
        done = worker_body["doneCriteria"]
        worker_body["doneCriteria"] = (done + [claim for claim in claims if claim not in done])[:LIST_LIMIT]
    workspace = body.get("workspace") or session["workspace_id"]
    if not gate.workspace_known(service, session["project_id"], workspace):
        raise GateError(404, "workspace_not_found", "Pracovní prostor v projektu neexistuje.",
                        "Použijte main, draft nebo ID pracovního prostoru projektu.")
    new_id, at = "tk_" + uuid.uuid4().hex, tokens.stamp(now)
    if machine["cardId"]:
        graph = service.view(session["project_id"], workspace)["graph"]
        machine |= neighbors(graph, machine["cardId"])
        design = design_ref(service, session["project_id"], graph, machine["cardId"])
        machine |= {"design": design} if design else {}

    def work(store):
        store.insert(new_id, workspace, "issued", worker_body, machine, at)
        return {"ticket": store.get(new_id)}
    return _write(service, session, work)


def _claims(service, project, intent):
    """Tvrzení `claim` kritérií záměru stránky (`page_intents.intent_claims`); neplatná verze či uzel = 422."""
    try:
        with service.registry_lock:
            claims = intent_claims(service.db, project, intent["workflowVersionId"], intent["nodeIds"])
    except (FlowInvalid, FlowNotFound) as error:
        raise GateError(422, "ticket_intent", str(error),
                        "Verzi a uzly intent.done ukáže opora_heart.py intent show PAGE (aktivní verze).") from None
    return [claim[:TEXT_LIMIT] for claim in claims]


def _pins(service, requested):
    """ID artefaktů Brainu → piny po pluginech s výchozím ponytailem (registr je list, pod zámkem projektu ne)."""
    try:
        with service.registry_lock:
            return pins.for_ticket(service.db, requested)
    except (LookupError, ValueError) as error:
        raise GateError(422, "invalid_payload", str(error),
                        "ID artefaktů a aktivní piny vrací GET /api/brain-registry/artifacts.") from None


def request(service, session, body, now=None):
    """`ticket.request`: ticket, který relace drží, jinak nejstarší vydaný v prostoru (nebere ho); nic = null."""
    shaped(body, (), hint='Tělo je {}: {"kind": "ticket.request"}.')
    project = session["project_id"]
    with service.reading(project):
        store = TicketStore(service.db_for(project), project)
        held = store.held_by(session["id"])
        ticket = held or store.oldest_issued(session["workspace_id"])
    return {"ticket": for_worker(ticket) if ticket else None, "held": held is not None}


def _holder_gone(db, session_id, at):
    """Relace držitele vypršela, je zneplatněná nebo neexistuje."""
    holder = GateSessionStore(db).get(session_id)
    return (holder is None or holder["revoked_at"] is not None
            or (holder["expires_at"] is not None and holder["expires_at"] <= at))


def _take_over(store, session, ticket, execution_id, at):
    """Převzetí drženého ticketu jinou relací (tatáž exekuce, nebo držitel už neplatí); jinak 409 `ticket_not_held`."""
    same_execution = execution_id is not None and execution_id == ticket["machine"]["executionId"]
    if not same_execution and not _holder_gone(store.db, ticket["sessionId"], at):
        raise GateError(409, "ticket_not_held", "Ticket drží jiná živá relace.", HELD_HINT)
    if execution_id and not same_execution:
        ticket_lifecycle.bind(store.db, store.project, ticket, execution_id)
    if not store.take_over(ticket["ticketId"], ticket["status"], ticket["sessionId"], session["id"], at,
                           execution_id):
        raise GateError(409, "ticket_state", "Ticket mezitím změnil stav.", "Načtěte ho znovu přes ticket.request.")
    emit_event(store.db, project_id=store.project, workspace_id=ticket["workspaceId"], kind="ticket.resumed",
               node_id=ticket["machine"]["cardId"], execution_id=execution_id or ticket["machine"]["executionId"],
               data={"ticketId": ticket["ticketId"], "fromSession": ticket["sessionId"], "toSession": session["id"]})


def claim(service, session, body, now=None):
    """`ticket.claim`: vydaný ticket připíše relaci (`issued` → `claimed`); uzavřený je 409 `ticket_state`.
    S `executionId` ho naváže na běžící exekuci karty ticketu (jinak 409 `ticket_execution`). Ticket držený
    jinou relací převezme (`_take_over`)."""
    wanted, execution_id = claim_payload(body)
    at = tokens.stamp(now)

    def work(store):
        ticket = _found(store, session, wanted)
        if ticket["status"] in HELD and ticket["sessionId"] not in (None, session["id"]):
            _take_over(store, session, ticket, execution_id, at)
            return {"ticket": for_worker(store.get(wanted))}
        advance(ticket["status"], "claimed")  # nejdřív stav (409 ticket_state), pak vazba na exekuci
        if execution_id:
            ticket_lifecycle.bind(store.db, store.project, ticket, execution_id)
        _walk(store, ticket, ("claimed",), at, session_id=session["id"], execution_id=execution_id)
        return {"ticket": for_worker(store.get(wanted))}
    return _write(service, session, work)


def release(service, session, body, now=None):
    """`ticket.release`: vzatý ticket se vrátí do fronty (`claimed` → `issued`) bez držitele a bez exekuce."""
    wanted, at = ticket_id(body, 'Například {"ticketId": "tk_…"}.'), tokens.stamp(now)

    def work(store):
        ticket = _held(store, session, wanted)
        advance(ticket["status"], "issued")
        if not store.unclaim(wanted, at):
            raise GateError(409, "ticket_state", "Ticket mezitím změnil stav.", "Načtěte ho znovu přes ticket.request.")
        return {"ticket": {"ticketId": wanted, "status": "issued"}}
    return _write(service, session, work)


def cancel(service, session, body, now=None):
    """`ticket.cancel` (jen srdce): práce, která už nedává smysl, skončí `cancelled`; odevzdaný ticket ne (409)."""
    wanted, at = ticket_id(body, 'Například {"ticketId": "tk_…"}.'), tokens.stamp(now)

    def work(store):
        ticket = _found(store, session, wanted)
        return {"ticket": {"ticketId": wanted, "status": _walk(store, ticket, ("cancelled",), at)}}
    return _write(service, session, work)


def feedback(service, session, body, now=None):
    """`ticket.feedback`: položka `bug|idea|improvement|question` s vlastním ID; otázka čeká na odpověď srdce."""
    wanted, kind, text = feedback_payload(body)
    item_id, at = "tf_" + uuid.uuid4().hex, tokens.stamp(now)

    def work(store):
        ticket = _held(store, session, wanted)
        targets = ("in_progress",) if ticket["status"] == "claimed" else ()
        if kind == "question" and ticket["status"] != "needs_answer":
            targets += ("needs_answer",)
        status = _walk(store, ticket, targets, at)
        store.add_feedback(item_id, wanted, kind, text, session["id"], at)
        return {"feedback": {"feedbackId": item_id, "kind": kind, "text": text, "answer": None},
                "ticket": {"ticketId": wanted, "status": status}}
    return _write(service, session, work)


def deliver(service, session, body, now=None):
    """`ticket.deliver`: odevzdání (`summary`, `sha?`) → `delivered`; s otevřenou otázkou 409 `ticket_state`.
    Ticket s prací Linie (`work`) a `sha`: commit projde `work.apply_report` (sha na větvi úkolu, jinak 409
    `work_mismatch`, nic se nezapíše); `delivered` neznamená hotovo, kuličku uzavře až začlenění službou."""
    wanted, delivery = deliver_payload(body)
    at = tokens.stamp(now)

    def work(store):
        ticket = _held(store, session, wanted)
        targets = ("in_progress", "delivered") if ticket["status"] == "claimed" else ("delivered",)
        if ticket.get("work") and delivery.get("sha"):
            reported = linie_work.apply_report(ticket["work"], delivery["sha"], [], None, at,
                                               "agent:" + (session.get("worker_name") or "?"))
            store.set_work(wanted, reported, at)
        _walk(store, ticket, targets, at, delivery={**delivery, "at": at})
        # Exekuce mohla být ověřená nebo sloučená dřív než odevzdání ticketu: stav ji dožene hned.
        return {"ticket": {"ticketId": wanted, "status": ticket_lifecycle.follow(store.db, store.project,
                                                                                 store.get(wanted), now)}}
    return _write(service, session, work)


def answer(service, session, body, now=None):
    """`ticket.answer` s `feedbackId` (srdce): odpověď na položku; poslední otázka vrátí ticket do `in_progress`."""
    wanted, item_id, text, at = body["ticketId"], body["feedbackId"], body["text"].strip(), tokens.stamp(now)

    def work(store):
        ticket = _found(store, session, wanted)
        item = store.feedback(item_id)
        if item is None or item["ticketId"] != wanted:
            raise GateError(404, "feedback_not_found", "Položka zpětné vazby u ticketu neexistuje.",
                            "ID položek jsou v GET /api/brain/tickets/{id} v poli feedback.")
        if not store.answer_feedback(item_id, {"text": text}, at):
            raise GateError(409, "feedback_answered", "Položka už má odpověď.", "Načtěte ticket znovu.")
        status = ticket["status"]
        if status == "needs_answer" and store.open_questions(wanted) == 0:
            status = _walk(store, ticket, ("in_progress",), at)
        return {"feedback": {"feedbackId": item_id, "kind": item["kind"], "text": item["text"],
                             "answer": {"text": text}},
                "ticket": {"ticketId": wanted, "status": status}}
    return _write(service, session, work)


def get(service, project, ticket_id_):
    """Celý ticket (tělo, strojová vrstva, držitel, odevzdání, zpětná vazba) pro čtení API; jinak 404."""
    if not service.project_exists(project):
        raise GateError(404, "project_not_found", "Projekt neexistuje.", "ID projektu najdete v GET /api/bootstrap.")
    with service.reading(project):
        ticket = TicketStore(service.db_for(project), project).get(ticket_id_)
    if ticket is None:
        raise GateError(404, "ticket_not_found", "Ticket v projektu neexistuje.", MISSING_HINT)
    return ticket


def list_tickets(service, project, workspace, status=None):
    """`{tickets}` pracovního prostoru od nejstaršího; neznámý stav je 422."""
    if status and status not in STATES:
        raise GateError(422, "invalid_payload", "Neznámý stav ticketu.", "Povolené stavy: " + ", ".join(STATES) + ".")
    if not service.project_exists(project):
        raise GateError(404, "project_not_found", "Projekt neexistuje.", "ID projektu najdete v GET /api/bootstrap.")
    if not gate.workspace_known(service, project, workspace):
        raise GateError(404, "workspace_not_found", "Pracovní prostor v projektu neexistuje.",
                        "Použijte main, draft nebo ID pracovního prostoru projektu.")
    with service.reading(project):
        return {"tickets": TicketStore(service.db_for(project), project).list(workspace, status or None)}
