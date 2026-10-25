"""Execution lease and result events at their point of change (docs/oporahub-events.md).

Called inside the execution transaction (`OporaExecutions.transaction`), so each event commits or
rolls back with the lease write it describes. Replays never reach these calls."""
import os
from datetime import UTC, datetime

from backend.canvas.opora_events import emit_event, refresh
from database.repositories import opora_events as store

# A renewal that changes nothing observable is told at most once per this many minutes per execution.
HEARTBEAT_EVENT_MINUTES = 15


def _emit(repo, kind, record, actor, **data):
    project, workspace = repo.scope
    return emit_event(repo.db, project_id=project, workspace_id=workspace, kind=kind, node_id=record["nodeId"],
                      execution_id=record["executionId"], actor=actor, data=data)


def claimed(repo, record, owner):
    _emit(repo, "lease.claimed", record, owner, epoch=record["epoch"], acceptedRevision=record["acceptedRevision"],
          expiresAt=record["expiresAt"])


def heartbeat_interval_seconds():
    """`OPORA_LEASE_HEARTBEAT_EVENT_MINUTES` (default 15); 0 tells every renewal, invalid values fall back."""
    try:
        minutes = float(os.environ.get("OPORA_LEASE_HEARTBEAT_EVENT_MINUTES", HEARTBEAT_EVENT_MINUTES))
    except ValueError:
        return HEARTBEAT_EVENT_MINUTES * 60
    return minutes * 60 if minutes >= 0 else HEARTBEAT_EVENT_MINUTES * 60


def heartbeat_reason(last, record, *, ttl, capped, previous_expires, stamp, now=None):
    """Why this renewal is worth an event, or None when it only keeps an unchanged lease alive.

    `last` is `(at, data)` of the execution's previous `lease.heartbeat` event. The lease itself is
    renewed either way; this only decides whether the feed hears about it."""
    if last is None:
        return "first"
    at, data = last
    if data.get("epoch") != record["epoch"]:
        return "epoch"
    if data.get("ttlSeconds") != ttl:
        return "ttl"
    if bool(data.get("capped")) != capped:
        return "capped"
    if previous_expires - stamp < ttl / 3:  # renewed with under a third of the lease left: beats were missed
        return "late"
    try:
        elapsed = ((now or datetime.now(UTC)) - datetime.fromisoformat(at)).total_seconds()
    except (TypeError, ValueError):
        return "keepalive"
    return "keepalive" if elapsed >= heartbeat_interval_seconds() else None


def heartbeat(repo, record, *, ttl, previous_expires, stamp):
    """A renewal emits `lease.heartbeat` only on an observable change or as the periodic keep-alive.

    A quiet renewal still recomputes the card (as the event used to), so stage and gate stay exact."""
    capped = record["expiresAt"] < stamp + ttl
    last = store.last_of_execution(repo.db, *repo.scope, record["executionId"], "lease.heartbeat")
    reason = heartbeat_reason(last, record, ttl=ttl, capped=capped, previous_expires=previous_expires, stamp=stamp)
    if reason is None:
        refresh(repo.db, *repo.scope, record["nodeId"])
        return None
    return _emit(repo, "lease.heartbeat", record, None, epoch=record["epoch"], expiresAt=record["expiresAt"],
                 ttlSeconds=ttl, capped=capped, reason=reason)


def expired(repo, node, owner):
    """The card's previous lease is past its deadline and is being replaced by a new claim."""
    project, workspace = repo.scope
    row = repo.db.execute("SELECT token,owner,expires_at FROM card_leases WHERE project_id=? AND workspace_id=?"
                          " AND node_id=?", (project, workspace, node)).fetchone()
    if row is None:
        return
    previous = next((item for item in repo.history(node) if item.get("token") == row[0]), None)
    emit_event(repo.db, project_id=project, workspace_id=workspace, kind="lease.expired", node_id=node,
               execution_id=previous["executionId"] if previous else None, actor=None,
               data={"expiredAt": row[2], "previousOwner": row[1], "replacedBy": owner})


def released(repo, record):
    refresh(repo.db, *repo.scope, record["nodeId"])


def reported(repo, record, receipt):
    _emit(repo, "result.reported", record, None, receiptId=receipt["receiptId"],
          acceptedRevision=receipt["acceptedRevision"])
