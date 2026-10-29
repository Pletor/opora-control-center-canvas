"""Co srdce budí a co dostane do dávky (docs/brain-heart.md §1).

`wake_input` převede událost outboxu na vstup: čekající lístek `ask` / `change` pracovníka (ne vlastní
eskalaci srdce) a úkol `failed`. `resolve` těsně před dávkou doplní k vstupům aktuální data z databáze (u selhaného úkolu
zadání i report, aby srdce nové zadání psalo z původního)
a zahodí ty, které mezitím vyřešil někdo jiný (lístek už zodpovězený). Zpráva člověka projde vždy.
"""
from database.repositories.gate_tickets import GateTicketStore
from database.repositories.heart_tasks import HeartTaskStore

TICKET_KINDS = ("ask", "change")


def wake_input(event):
    """Vstup dávky z události `{kind, data, workspaceId}`, nebo None (událost srdce nebudí)."""
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    if (event.get("kind") == "gate.ticket" and data.get("status") == "queued" and data.get("kind") in TICKET_KINDS
            and data.get("from") != "heart" and isinstance(data.get("ticketId"), str)):
        return {"type": "ticket", "ticketId": data["ticketId"], "kind": data["kind"]}
    if event.get("kind") == "gate.task" and data.get("status") == "failed" and isinstance(data.get("taskId"), str):
        return {"type": "taskFailed", "taskId": data["taskId"]}
    return None


def _ticket(store, item):
    ticket = store.get(item["ticketId"])
    if ticket is None or ticket["status"] != "queued":
        return None
    return {**item, "body": ticket["body"]}


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
            value = _ticket(tickets, item) if kind == "ticket" else _task(tasks, item) if kind == "taskFailed" else item
            if value is not None:
                resolved.append(value)
    return resolved
