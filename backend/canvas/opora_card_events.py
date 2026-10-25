"""`card.closed` when a human confirms a card done (docs/oporahub-events.md).

Called from the Desktop v3 state write inside its transaction: a `done.confirmed` false → true
transition emits `card.closed` (and resolves the `close_card` decision); a reopened card only
re-evaluates its stage."""
from backend.canvas.opora_events import emit_event, refresh


def _confirmed(state, node):
    return bool(state.get("nodes", {}).get(node, {}).get("done", {}).get("confirmed"))


def closures(db, project, workspace, before, after, actor):
    for node in sorted(set(before.get("nodes", {})) | set(after.get("nodes", {}))):
        was, now = _confirmed(before, node), _confirmed(after, node)
        if was == now:
            continue
        if not now:
            emit_event(db, project_id=project, workspace_id=workspace, kind="card.reopened", node_id=node,
                       actor=actor, data={"previouslyConfirmed": True})
            refresh(db, project, workspace, node, actor)
            continue
        done = after["nodes"][node]["done"]
        emit_event(db, project_id=project, workspace_id=workspace, kind="card.closed", node_id=node, actor=actor,
                   data={"by": done.get("by"), "at": done.get("at")})
        awaiting = db.execute("SELECT execution_id FROM opora_execution_pull_requests WHERE project_id=? AND"
                              " workspace_id=? AND node_id=? AND awaiting_human_close=1 ORDER BY execution_id",
                              (project, workspace, node)).fetchone()
        if awaiting is not None:  # The close_card decision exists only after a merge write-back.
            emit_event(db, project_id=project, workspace_id=workspace, kind="decision.resolved", node_id=node,
                       execution_id=awaiting[0], actor=actor, data={"decision": "close_card"})
