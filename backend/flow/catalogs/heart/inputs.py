"""Co srdce budí a co dostane do dávky (docs/brain-heart.md §1).

`wake_input` převede událost outboxu na vstup: čekající lístek `ask` / `change` pracovníka (ne vlastní
eskalaci srdce), selhaný ticket práce (`ticket.failed` → vstup `workFailed`), chybu plátna 2–4 (`canvas.failed` z
`backend/flow/canvas_log.py` → vstup `canvasFailed`, třeba neprošlý uzel záměru stránky) a sloučení karty `merge.done` (docs/brain-heart-orchestrator.md §4). Ticket práce
(docs/navrhy/2026-11-03-novy-zaklad.md §3.3) budí otázkou dělníka (`ticket.feedback` typu `question` → vstup
`workQuestion` s textem a `feedbackId`, zodpovězená mezitím vypadne) a odevzdáním (`ticket.deliver` → `workDelivered`
se shrnutím a sha); obojí z auditní události `gate.ticket` druhu brány. `resolve` těsně před dávkou doplní k vstupům aktuální data z databáze (u selhaného ticketu
tělo, důvod a odevzdání, aby srdce nový ticket psalo z původního), k lístku zkratku vstupu brány (`intake`: ID, stanovisko,
podobné vstupy) a zahodí ty, které mezitím vyřešil někdo jiný (lístek už zodpovězený). Zpráva člověka projde vždy.
`backlog` po startu srdce dohání to, co outbox už nepřinese (událost vznikla před prvním čtením kurzoru,
třeba při restartu serveru): čekající lístky a nedávné zprávy člověka, které žádná dávka `ok` ještě neviděla.
`milestone_wakes` je deterministický vstup bez vlastní události outboxu (spouštěč `milestone.done`,
docs/navrhy/2026-10-30-metriky-a-spoustece.md §4): srdce (`wakes.py`) ho spočítá po události `card.closed` a při prvním
čtení projektu; splněný aktivní milník budí srdce jednou (`heart_triggers`) s odloženými požadavky k otevření.
Stejnou cestou jdou spouštěče karet (`card_wakes`, `determinism/triggers.py`: too_big, retry, step_failed, stalled,
over_budget) po událostech běhu a plánu (`TRIGGER_EVENTS`) a ruční změna plánu (`human_changes`: `changeset.accepted`,
jejíž revizi přijal člověk).
Spouštěč výslechu (docs/navrhy/2026-10-30-vyslech-srdce.md §2) dává vstup `brief`: `brief_wakes` pro požadavky
(nový, otevřené rozšíření, `changes_intent`) se spisem a krátký výslech karty `ready` s tenkými podklady přes
`card_wakes` (`brief.card_hit`); obojí jednou na stav (`heart_triggers`). Odpověď člověka na otázku výslechu
a „Vyslechni mě k tomu“ z Velínu budí přes `brief_wakes` také, jednou na odpověď a jednou na žádost.
Prázdná fronta (`idle_wakes`, `determinism/idle.py`, OPORA-002): přijatý plán bez karty k převzetí a bez běhu budí
srdce vstupem `idle` jednou na revizi plánu a počet sloučených karet, aby naplánovalo další kartu.
"""
from datetime import UTC, datetime, timedelta

from backend.brain_opora.determinism import (
    brain_files,
    brief,
    brief_setting,
    idle,
    intake,
    milestones,
    triggers,
)
from backend.brain_opora.determinism import brief_vault_link as vault_link
from database.repositories.gate_tickets import GateTicketStore
from database.repositories.tickets import TicketStore

TICKET_KINDS = ("ask", "change")
WORK_INPUTS = {"ticket.feedback": "workQuestion", "ticket.deliver": "workDelivered"}  # ticket práce (§3.3)
BACKLOG = 50  # nejvýš čekajících lístků dohnaných po startu
MESSAGE_HOURS = 24  # zprávy člověka starší než tolik hodin se po startu nedohánějí


def wake_input(event):
    """Vstup dávky z události `{kind, data, workspaceId}`, nebo None (událost srdce nebudí)."""
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    if (event.get("kind") == "gate.ticket" and data.get("status") == "queued" and data.get("kind") in TICKET_KINDS
            and data.get("from") != "heart" and isinstance(data.get("ticketId"), str)):
        return {"type": "ticket", "ticketId": data["ticketId"], "kind": data["kind"]}
    if (event.get("kind") == "gate.ticket" and data.get("status") == "queued" and data.get("from") != "heart"
            and isinstance(data.get("ticketId"), str)
            and (data.get("kind") == "ticket.deliver"
                 or (data.get("kind") == "ticket.feedback" and data.get("feedbackKind") == "question"))):
        return {"type": WORK_INPUTS[data["kind"]], "requestId": data["ticketId"]}
    if event.get("kind") == "ticket.failed" and isinstance(data.get("ticketId"), str):
        return {"type": "workFailed", "ticketId": data["ticketId"], "reason": str(data.get("reason") or "")}
    if event.get("kind") == "canvas.failed":
        return {"type": "canvasFailed", "canvas": data.get("canvas"), "kind": data.get("kind"),
                "payload": data.get("payload")}
    if event.get("kind") == "merge.done":
        # PR karty nebo lokální sloučení; data se před dávkou nedočítají (`resolve` je nechá projít).
        return {"type": "merged", "nodeId": event.get("nodeId"), "executionId": event.get("executionId"),
                "mergeSha": data.get("mergeSha") or data.get("commit"), "pr": event.get("prNumber")}
    return None


def closed_workspaces(events):
    """Prostory, ve kterých se uzavřela karta (`card.closed`): jen tam se může splnit kritérium milníku."""
    return {event.get("workspaceId") for event in events if event.get("kind") == "card.closed"}


def milestone_wakes(service, project, workspaces, at):
    """`[(prostor, vstup milestoneDone)]` pro splněné aktivní milníky, kterým srdce ještě nebudilo
    (`workspaces` None = všechny prostory); značku „už jsem budil“ zapíše ve stejné transakci."""
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            return milestones.wakes(db, project, workspaces, at)


# Události, po kterých se může změnit štítek, stav karty nebo počet selhání (release se hlásí jen `stage.changed`).
TRIGGER_EVENTS = ("changeset.accepted", "lease.claimed", "lease.expired", "result.reported", "stage.changed",
                  "card.reopened")


def trigger_workspaces(events):
    """Prostory, ve kterých se po `events` vyplatí znovu vyhodnotit spouštěče karet."""
    return {event.get("workspaceId") for event in events if event.get("kind") in TRIGGER_EVENTS}


def card_wakes(service, project, workspaces, at, now):
    """`[(prostor, vstup cardTrigger)]` spouštěčů karet, kterým srdce ještě nebudilo (`workspaces` None = prostory
    s přijatým plánem); značky zapíše v jedné transakci. Vypnutý výslech (`brain.brief`) tenké karty nebudí."""
    enabled = brief_setting.read(service, project)["enabled"]
    return triggers.wakes(service, project, workspaces, at, now, extra=brief.card_hit if enabled else None)


def idle_wakes(service, project, at, now):
    """`([(prostor, vstup idle)], {prostor: důvod})` za prázdnou frontu prostorů s přijatým plánem (`idle.wakes`)."""
    with service.reading(project):
        workspaces = triggers.spaces(service.db_for(project), project)
    return idle.wakes(service, project, workspaces, at, now)


def brief_wakes(service, project, at, now):
    """`[(prostor, vstup brief)]` požadavků, které podle `brief.needs_brief` potřebují výslech a srdce na ten stav
    ještě nebudilo (jen se vstupem z posledních `brief.WINDOW_HOURS` h). Kandidáti se čtou bez zámku, spis mimo
    zámek, značka a spis `draft` se zapíší v jedné transakci. Vypnutý výslech (`brain.brief`) nebudí nic.
    Kanál člověka z Velínu (řez 3, `brief.human_wakes`) budí vždy: jednou na odpověď na otázku výslechu
    a jednou na žádost „Vyslechni mě k tomu“; tyto vstupy jdou v dávce první."""
    enabled = brief_setting.read(service, project)["enabled"]
    since = (datetime.fromtimestamp(now, UTC) - timedelta(hours=brief.WINDOW_HOURS)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    with service.reading(project):
        db = service.db_for(project)
        candidates = brief.requirement_wakes(db, since) if enabled else []
        human = brief.human_wakes(db)
    if not candidates and not human:
        return []
    files = {item["id"]: brief.collect_situation(service, project, space, item["id"]) for space, item, _ in candidates}
    found = []
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            found += brief.fire_human(db, human, at)
            for space, item, reason in candidates:
                value = brief.open_brief(db, space, item, reason, files[item["id"]], at)
                if value is not None:
                    found.append((space, value))
    # Výslech ve Schránce (řez 1): nový spis dostane kořenový fragment požadavku hned, mimo zámek; chyba nic nezastaví.
    for space, value in found:
        if value.get("requirementId") and value.get("reason") not in ("answer", "asked"):
            vault_link.safely(vault_link.ensure_root, service, project, space, value["requirementId"])
    return found


def human_changes(service, project, events, at):
    """`[(prostor, vstup humanChange)]` za přijetí plánu člověkem (`changeset.accepted`), jednou na revizi."""
    accepted = [(event["workspaceId"], (event.get("data") or {}).get("acceptedHead")) for event in events
                if event.get("kind") == "changeset.accepted"]
    if not accepted:
        return []
    found = []
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            for workspace, revision in accepted:
                item = triggers.human_change(db, project, workspace, revision, at) if revision else None
                if item is not None:
                    found.append((workspace, item))
    return found


def _ticket(store, item, db):
    ticket = store.get(item["ticketId"])
    if ticket is None or ticket["status"] != "queued":
        return None
    found = intake.for_source(db, "gate_" + str(item.get("kind")), item["ticketId"])
    return {**item, "body": ticket["body"]} | ({"intake": found} if found else {})


def _failed(work, item):
    """Selhaný ticket práce s tělem a odevzdáním; ticket mezitím v jiném stavu vypadne."""
    ticket = work.get(item["ticketId"])
    if ticket is None or ticket["status"] != "failed":
        return None
    return {**item, "status": ticket["status"], "cardId": ticket["machine"]["cardId"],
            "executionId": ticket["machine"]["executionId"], "body": ticket["body"], "delivery": ticket["delivery"]}


def _work(gate_tickets, work, item):
    """Otázka dělníka k ticketu práce (ještě bez odpovědi) nebo odevzdání ticketu: data z auditu brány a z ticketu."""
    audit = gate_tickets.get(item["requestId"])
    answer = audit["answer"] if audit and isinstance(audit["answer"], dict) else {}
    ticket = work.get((answer.get("ticket") or {}).get("ticketId"))
    if ticket is None:
        return None
    base = {"type": item["type"], "ticketId": ticket["ticketId"], "status": ticket["status"],
            "cardId": ticket["machine"]["cardId"], "executionId": ticket["machine"]["executionId"]}
    if item["type"] == "workQuestion":
        found = work.feedback((answer.get("feedback") or {}).get("feedbackId"))
        if found is None or found["answer"] is not None:
            return None
        return base | {"feedbackId": found["feedbackId"], "kind": found["kind"], "text": found["text"],
                       "essence": ticket["body"]["essence"]}
    return base | {"delivery": ticket["delivery"]}


def resolve(service, project, items):
    """Vstupy s aktuálními daty; vyřešené mezitím vypadnou. Pořadí zůstává."""
    resolved = []
    with service.reading(project):
        db = service.db_for(project)
        tickets, work = GateTicketStore(db, project), TicketStore(db, project)
        for item in items:
            kind = item.get("type")
            if kind == "researchPlanning":
                from backend.editor.research.continuations import listing
                receipts = listing(service, project, item["workspace"])
                if not any(r["id"] == item["continuationId"] and r["status"] in ("pending", "running")
                           for r in receipts):
                    continue
            value = (_ticket(tickets, item, db) if kind == "ticket" else _failed(work, item) if kind == "workFailed"
                     else _work(tickets, work, item) if kind in WORK_INPUTS.values() else item)
            if value is not None:
                resolved.append(value)
    return resolved


def _handled(journal):
    """`(lístky, zprávy)`, které viděla dávka se stavem `ok`: ID lístků a `{(prostor, text): nejpozdější at}`."""
    tickets, messages = set(), {}
    for entry in journal:
        if entry.get("status") != "ok" or not isinstance(entry.get("inputs"), list):
            continue
        for item in entry["inputs"]:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "ticket":
                tickets.add(item.get("ticketId"))
            elif item.get("type") == "message":
                key = (entry.get("workspace"), item.get("text"))
                messages[key] = max(messages.get(key, ""), str(entry.get("at") or ""))
    return tickets, messages


def backlog(service, project, brain, since):
    """`[(prostor, vstup)]` k dohnání po startu: čekající lístky pracovníků a zprávy člověka novější než `since`
    (ISO čas), které žádná dávka `ok` neměla ve vstupech. Lístek zodpovězený mezitím vyřadí až `resolve`."""
    journal = brain_files.journal(brain, None)
    tickets, messages = _handled(journal)
    with service.reading(project):
        waiting = GateTicketStore(service.db_for(project), project).waiting_for_heart(TICKET_KINDS, BACKLOG)
    found = [(space, {"type": "ticket", "ticketId": ticket["ticketId"], "kind": ticket["kind"]})
             for space, ticket in waiting if ticket["ticketId"] not in tickets]
    for entry in brain_files.messages(brain, None, None):
        at, space, text = str(entry.get("at") or ""), entry.get("workspace"), entry["text"]
        if entry.get("duplicate"):
            continue  # stejná věta, kterou vstupní brána označila `duplicate`, srdce nebudí
        if at >= since and isinstance(space, str) and messages.get((space, text), "") < at:
            found.append((space, {"type": "message", "text": text}))
    return found
