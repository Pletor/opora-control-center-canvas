"""Execution lease and result events at their point of change (docs/oporahub-events.md).

Called inside the execution transaction (`OporaExecutions.transaction`), so each event commits or
rolls back with the lease write it describes. Replays never reach these calls."""
from backend.canvas.opora_events import emit_event, refresh


def _emit(repo, kind, record, actor, **data):
    project, workspace = repo.scope
    return emit_event(repo.db, project_id=project, workspace_id=workspace, kind=kind, node_id=record["nodeId"],
                      execution_id=record["executionId"], actor=actor, data=data)


def claimed(repo, record, owner):
    _emit(repo, "lease.claimed", record, owner, epoch=record["epoch"], acceptedRevision=record["acceptedRevision"],
          expiresAt=record["expiresAt"])


def heartbeat(repo, record):
    _emit(repo, "lease.heartbeat", record, None, epoch=record["epoch"], expiresAt=record["expiresAt"])


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
