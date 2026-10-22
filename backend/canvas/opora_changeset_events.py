"""Spec changeset events at the repository write (docs/oporahub-events.md).

`changeset.proposed` (+ `decision.created`, the human acceptance it waits for) fires on every new
proposal row, including rebased and auto-rebased siblings. `changeset.accepted` (+
`decision.resolved`) fires when the accepted head advances to a revision that accepts a proposal
(spec, graph and content acceptance all advance the same ref). A new head can make reported
evidence stale, so the cards the feed already tracks are re-evaluated."""
from backend.canvas.opora_events import emit_event, refresh


def _nodes(record):
    return sorted({item["nodeId"] for item in record.get("changes", []) if isinstance(item, dict) and "nodeId" in item})


def proposed(db, scope, record):
    data = {"proposalId": record["id"], "subject": record.get("subject"), "parentRevision": record.get("parentRevision"),
            "supersedes": record.get("supersedes"), "nodeIds": _nodes(record)}
    for kind, extra in (("changeset.proposed", {}), ("decision.created", {"decision": "accept"})):
        emit_event(db, project_id=scope[0], workspace_id=scope[1], kind=kind, actor=record.get("by"),
                   data={**data, **extra})


def advanced(db, scope, revision_id):
    row = db.execute("SELECT proposal_id FROM opora_spec_revisions WHERE project_id=? AND workspace_id=? AND id=?",
                     (*scope, revision_id)).fetchone()
    if row is not None and row[0] is not None:
        data = {"proposalId": row[0], "acceptedHead": revision_id}
        emit_event(db, project_id=scope[0], workspace_id=scope[1], kind="changeset.accepted", actor="human", data=data)
        emit_event(db, project_id=scope[0], workspace_id=scope[1], kind="decision.resolved", actor="human",
                   data={**data, "decision": "accept"})
    tracked = db.execute("SELECT node_id FROM opora_event_card_state WHERE project_id=? AND workspace_id=? UNION "
                         "SELECT node_id FROM opora_executions WHERE project_id=? AND workspace_id=?",
                         (*scope, *scope)).fetchall()
    for node in sorted({item[0] for item in tracked}):
        refresh(db, *scope, node)
