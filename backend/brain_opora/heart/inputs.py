"""Co srdce budí a co dostane do dávky (docs/brain-heart.md §1).

`wake_input` převede událost outboxu na vstup: čekající lístek `ask` / `change` pracovníka (ne vlastní
eskalaci srdce), úkol `failed` a sloučení karty `merge.done` (docs/brain-heart-orchestrator.md §4). `resolve` těsně před dávkou doplní k vstupům aktuální data z databáze (u selhaného úkolu
zadání i report, aby srdce nové zadání psalo z původního), k lístku zkratku vstupu brány (`intake`: ID, stanovisko,
podobné vstupy) a zahodí ty, které mezitím vyřešil někdo jiný (lístek už zodpovězený). Zpráva člověka projde vždy.
`backlog` po startu supervisoru dohání to, co outbox už nepřinese (událost vznikla před prvním čtením kurzoru,
třeba při restartu serveru): čekající lístky a nedávné zprávy člověka, které žádná dávka `ok` ještě neviděla.
`milestone_wakes` je deterministický vstup bez vlastní události outboxu (spouštěč `milestone.done`,
docs/navrhy/2026-10-30-metriky-a-spoustece.md §4): supervisor ho spočítá po události `card.closed` a při prvním
čtení projektu; splněný aktivní milník budí srdce jednou (`heart_triggers`) s odloženými požadavky k otevření.
Stejnou cestou jdou spouštěče karet (`card_wakes`, `determinism/triggers.py`: too_big, retry, stalled,
over_budget) po událostech běhu a plánu (`TRIGGER_EVENTS`) a ruční změna plánu (`human_changes`: `changeset.accepted`,
jejíž revizi přijal člověk).
"""
from backend.brain_opora.determinism import brain_files, intake, milestones, triggers
from database.repositories.gate_tickets import GateTicketStore
from database.repositories.heart_tasks import HeartTaskStore

TICKET_KINDS = ("ask", "change")
BACKLOG = 50  # nejvýš čekajících lístků dohnaných po startu
MESSAGE_HOURS = 24  # zprávy člověka starší než tolik hodin se po startu nedohánějí


def wake_input(event):
    """Vstup dávky z události `{kind, data, workspaceId}`, nebo None (událost srdce nebudí)."""
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    if (event.get("kind") == "gate.ticket" and data.get("status") == "queued" and data.get("kind") in TICKET_KINDS
            and data.get("from") != "heart" and isinstance(data.get("ticketId"), str)):
        return {"type": "ticket", "ticketId": data["ticketId"], "kind": data["kind"]}
    if event.get("kind") == "gate.task" and data.get("status") == "failed" and isinstance(data.get("taskId"), str):
        return {"type": "taskFailed", "taskId": data["taskId"]}
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
    s přijatým plánem); značky zapíše v jedné transakci."""
    return triggers.wakes(service, project, workspaces, at, now)


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


def _task(store, item):
    task = store.get(item["taskId"])
    if task is None or task["status"] != "failed":
        return None
    return {**item, "title": task["title"], "body": task["body"], "report": task["report"]}


def resolve(service, project, items):
    """Vstupy s aktuálními daty; vyřešené mezitím vypadnou. Pořadí zůstává."""
    resolved = []
    with service.reading(project):
        db = service.db_for(project)
        tickets, tasks = GateTicketStore(db, project), HeartTaskStore(db, project)
        for item in items:
            kind = item.get("type")
            value = _ticket(tickets, item, db) if kind == "ticket" else _task(tasks, item) if kind == "taskFailed" else item
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
