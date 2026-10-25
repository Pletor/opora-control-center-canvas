"""OporaHub events outbox: `emit_event` records one change in the same SQLite transaction as the change.

Contract: docs/oporahub-events.md. Services call `emit_event` at the point of change (never by
diffing snapshots); `agent-state` stays the snapshot, events are the delta. After a source event
that names a card, `opora_event_stage.refresh_card` recomputes that one card's stage and gate and
emits `stage.changed` / `gate.changed` only when they differ from the last emitted value.

Stable signature for other modules (e.g. plan steps):

    emit_event(conn_or_service, *, project_id, workspace_id, kind, node_id=None, execution_id=None,
               step_id=None, pr_number=None, stage=None, health=None, actor=None, data=None) -> int

`conn_or_service` is a sqlite3 connection, an object with `.db` (repositories) or the canvas
service (`db_for(project_id)` is used). Inside an open transaction the row joins it; otherwise
the event is committed on its own. Returns the event cursor id.
"""
import os
from datetime import UTC, datetime, timedelta

from backend.canvas.process_signal import PROCESS_SIGNAL
from database.repositories import opora_events as store

KINDS = ("stage.changed", "step.started", "step.done", "step.failed", "lease.claimed", "lease.heartbeat",
         "lease.expired", "result.reported", "pr.linked", "review.round", "review.finding", "gate.changed",
         "formal.result", "decision.created", "decision.resolved", "changeset.proposed", "changeset.accepted",
         "autorebase.done", "autorebase.conflict", "merge.done", "writeback.done", "card.closed",
         "memory.recall", "memory.write", "plan.commit", "card.reopened", "harness.fixture.observed")
# Derived kinds never trigger a refresh themselves; step progress is not a loop stage.
DERIVED = {"stage.changed", "gate.changed", "step.started", "step.done", "step.failed"}
# Live process (docs/zivy-proces.md): memory and legacy plan commits come from the activity bridge and
# never move a card's stage; events of external sources (office, github) never refresh a card either.
QUIET = DERIVED | {"memory.recall", "memory.write", "plan.commit", "harness.fixture.observed"}
EXTERNAL_SOURCES = ("office", "github")
SYSTEM = {"kind": "system", "name": "opora"}
ACTOR_KINDS = ("human", "agent", "system")
RETENTION_DAYS = 14
MAX_ROWS = 50_000
PRUNE_EVERY = 256  # Retention runs on every N-th event, inside the same transaction.


def retention():
    """`(days, max_rows)` from OPORA_EVENTS_RETENTION_DAYS / OPORA_EVENTS_MAX_ROWS (positive ints)."""
    def number(name, default):
        try:
            value = int(os.environ.get(name, default))
        except ValueError:
            return default
        return value if value > 0 else default
    return number("OPORA_EVENTS_RETENTION_DAYS", RETENTION_DAYS), number("OPORA_EVENTS_MAX_ROWS", MAX_ROWS)


def stamp(moment=None):
    return (moment or datetime.now(UTC)).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def actor_of(value):
    """`{kind, name}`: a dict passes through, `"agent:worker"`-style owners become agents, None is the system."""
    if isinstance(value, dict) and value.get("kind") in ACTOR_KINDS:
        return {"kind": value["kind"], "name": value.get("name") if isinstance(value.get("name"), str) else None}
    if isinstance(value, str) and value:
        kind = value if value in ACTOR_KINDS else "agent"
        return {"kind": kind, "name": None if value in ACTOR_KINDS else value[:160]}
    return dict(SYSTEM)


def connection(conn_or_service, project_id):
    if hasattr(conn_or_service, "db_for"):
        return conn_or_service.db_for(project_id)
    return getattr(conn_or_service, "db", conn_or_service)


def emit_event(conn_or_service, *, project_id, workspace_id, kind, node_id=None, execution_id=None, step_id=None,
               pr_number=None, stage=None, health=None, actor=None, data=None, process=None):
    """`process` (live process): {source, phase, state, title, detail, refs, tool, external_id}. Only accepted
    office/GitHub events that already passed `process_event_validation` may carry their own `kind`."""
    external = bool(process) and process.get("source") in EXTERNAL_SOURCES
    if kind not in KINDS and not external:
        raise ValueError(f"Unknown OporaHub event kind: {kind}")
    if not isinstance(project_id, str) or not isinstance(workspace_id, str):
        raise TypeError("An event needs project_id and workspace_id.")
    db = connection(conn_or_service, project_id)
    event = {"at": stamp(), "projectId": project_id, "workspaceId": workspace_id, "kind": kind, "nodeId": node_id,
             "executionId": execution_id, "stepId": step_id,
             "prNumber": pr_number if isinstance(pr_number, int) else None, "stage": stage, "health": health,
             "actor": actor_of(actor), "data": dict(data or {}), "process": process}

    def write():
        identifier = store.insert(db, event)
        from backend.canvas.opora_event_projections import project
        project(db, identifier, event)
        if identifier % PRUNE_EVERY == 0:
            days, rows = retention()
            store.prune(db, stamp(datetime.now(UTC) - timedelta(days=days)), rows)
        if node_id is not None and kind not in QUIET and not external:
            from backend.canvas.opora_event_stage import refresh_card
            refresh_card(db, project_id, workspace_id, node_id, actor=event["actor"])
        return identifier

    if db.in_transaction:
        identifier = write()
        PROCESS_SIGNAL.notify()  # visible after the caller commits; the stream's poll is the safety net
        return identifier
    with db:
        identifier = write()
    PROCESS_SIGNAL.notify()
    return identifier


def refresh(conn_or_service, project_id, workspace_id, node_id, actor=None):
    """Recompute one card after a write that has no event of its own (release, PR closed, self-checks)."""
    from backend.canvas.opora_event_stage import refresh_card
    db = connection(conn_or_service, project_id)
    if db.in_transaction:
        return refresh_card(db, project_id, workspace_id, node_id, actor=actor_of(actor))
    with db:
        return refresh_card(db, project_id, workspace_id, node_id, actor=actor_of(actor))


def refresh_targets(db, project_id, workspace_id, *, execution_id=None, pr_number=None):
    """Refresh the card(s) behind an execution or a linked PR number after a gate input changed."""
    from backend.canvas.opora_event_stage import node_of_execution, nodes_of_pull_request
    nodes = []
    if execution_id is not None:
        nodes = [node for node in [node_of_execution(db, project_id, workspace_id, execution_id)] if node]
    if pr_number is not None:
        nodes = nodes_of_pull_request(db, project_id, workspace_id, pr_number)
    for node in nodes:
        refresh(db, project_id, workspace_id, node)
    return nodes
