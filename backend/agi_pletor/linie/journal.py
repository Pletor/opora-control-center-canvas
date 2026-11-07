"""Deník Linie (docs/navrhy/2026-11-06-linie-rebrand.md §7 bod 5): události `linie.*` v outboxu `opora_events`.

Řádek má stabilní `id` (AUTOINCREMENT), `kind`, `at` a `data = {refs: {ticket?, request?, op?, env?, sha?}, by, …}`;
událost nemusí mít kuličku. Zápis jde přímo přes repozitář outboxu (`emit_event` zná jen druhy OporaHubu a karta se
z události Linie nepřepočítává). `write` se připojí k transakci volajícího, `record` si otevře vlastní. `read` vrací
události po `after` v pořadí `id` a `lastId` (bez nových zůstává `after`): „nových“ se počítá od id, ne od času.
"""
import json

from backend.canvas.opora_events import actor_of, stamp
from database.repositories import opora_events as store

PREFIX = "linie."
LIMIT = 500


def _actor(by):
    """`human` → člověk, `agent:<jméno>` → agent se jménem, jinak služba OPORA."""
    if by == "human":
        return {"kind": "human", "name": None}
    if isinstance(by, str) and by.startswith("agent:"):
        return {"kind": "agent", "name": by.split(":", 1)[1][:160] or None}
    return actor_of(None)


def write(db, project, kind, by, refs, workspace="main", **data):
    """Událost v otevřené transakci `db`; vrací její `id`."""
    assert kind.startswith(PREFIX), kind
    return store.insert(db, {"at": stamp(), "projectId": project, "workspaceId": workspace or "main", "kind": kind,
                             "nodeId": None, "executionId": None, "stepId": None, "prNumber": None, "stage": None,
                             "health": None, "actor": _actor(by),
                             "data": {"refs": {k: v for k, v in refs.items() if v is not None}, "by": by, **data}})


def record(service, project, kind, by, refs, workspace="main", **data):
    """Událost ve vlastní transakci pod zámkem projektu (operace, jejichž záznam je JSON mimo SQLite)."""
    with service.lock_for(project):
        db = service.db_for(project)
        with db:
            return write(db, project, kind, by, refs, workspace, **data)


def read(service, project, after=0, limit=100):
    """`{events: [{id, kind, at, by, refs, data}], lastId}` po `after` v pořadí `id`."""
    limit = max(1, min(int(limit), LIMIT))
    with service.reading(project):
        rows = service.db_for(project).execute(
            "SELECT id, at, kind, data FROM opora_events WHERE project_id=? AND kind LIKE 'linie.%' AND id>?"
            " ORDER BY id LIMIT ?", (project, int(after), limit)).fetchall()
    events = []
    for identifier, at, kind, raw in rows:
        data = json.loads(raw)
        events.append({"id": identifier, "kind": kind, "at": at, "by": data.pop("by", None),
                       "refs": data.pop("refs", {}), "data": data})
    return {"events": events, "lastId": events[-1]["id"] if events else int(after)}
