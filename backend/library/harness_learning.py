"""Native outbox -> durable selected-kit outcomes in the caller's transaction.

External office/GitHub event envelopes cannot assert native verification. Selected resources
are associated with outcomes; neither actual invocation nor causal contribution is inferred.
"""
import json

from backend.canvas.opora_execution_lineage import validate_accepted_lineage
from backend.library.harness_kit import kit_of_assignment
from database.repositories import harness_learning as store
from database.repositories import harness_memory
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_executions import Executions

KINDS = {"lease.claimed", "result.reported", "decision.resolved", "card.reopened"}


def _record(db, event):
    if not event.get("executionId"):
        return None
    try:
        record = Executions(db, event["projectId"], event["workspaceId"]).read(event["executionId"])
    except ValueError:
        return None
    if record["nodeId"] != event["nodeId"] or record.get("contextProtocolVersion") != 2:
        return None
    return record


def _reported(db, record, event):
    row = db.execute("SELECT record FROM opora_execution_results WHERE project_id=? AND workspace_id=?"
                     " AND execution_id=? AND json_extract(record,'$.receiptId')=?",
                     (record["project"], record["workspace"], record["executionId"],
                      event["data"].get("receiptId"))).fetchone()
    if row is None:
        return "unknown"
    receipt = json.loads(row[0])
    if receipt.get("assignmentDigest") != record["assignmentDigest"]:
        return "unknown"
    steps = record["assignment"].get("steps") or []
    items = receipt["result"].get("stepResults") or []
    if any(item["status"] == "failed" for item in items):
        return "fail"
    if (steps and {item["stepId"] for item in items} == {step["id"] for step in steps}
            and all(item["status"] == "done" for item in items)):
        return "pass"
    return "unknown"


def _closed(db, record, event):
    if event["actor"]["kind"] != "human" or event["data"].get("decision") != "close_card":
        return False
    scope = record["project"], record["workspace"]
    # A card with several unresolved merged runs cannot be attributed to an arbitrary first row.
    links = db.execute("SELECT execution_id,accepted_revision,merge_sha FROM opora_execution_pull_requests"
                       " WHERE project_id=? AND workspace_id=? AND node_id=? AND state='merged'"
                       " AND awaiting_human_close=1", (*scope, record["nodeId"])).fetchall()
    if (len(links) != 1 or links[0][0] != record["executionId"]
            or links[0][1] != record["acceptedRevision"] or not links[0][2]):
        return False
    revisions = ChangesetRepository(db, *scope)
    head = revisions.head()
    if head is None:
        return False
    try:
        validate_accepted_lineage(db, *scope, record["nodeId"], record["acceptedRevision"], head)
    except ValueError:
        return False
    return True


def project_event(db, event_id, event):
    """Registry callback: no I/O beyond the source SQLite connection; no independent commits."""
    if event["kind"] not in KINDS or event.get("process") or event.get("source", "opora") != "opora":
        return
    # Minimal outbox-only databases used by older modules cannot contain a pinned Harness run.
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='harness_learning_runs' AND type='table'").fetchone() is None:
        return
    if not db.in_transaction:
        raise RuntimeError("Harness projection requires the source event transaction.")
    if event["kind"] == "card.reopened":
        if event["actor"]["kind"] != "human":
            return
        rows = db.execute("SELECT execution_id FROM harness_learning_runs WHERE project_id=? AND workspace_id=? AND node_id=?",
                          (event["projectId"], event["workspaceId"], event["nodeId"])).fetchall()
        if not rows or not store.applied(db, event_id, event):
            return
        for row in rows:
            scope = event["projectId"], event["workspaceId"], row[0]
            if store.outcome(db, scope, "verified", "unknown", event_id, "human-close-withdrawn", event["at"]):
                harness_memory.enqueue(db, scope, event_id, "unknown", event["at"])
        return
    record = _record(db, event)
    if record is None:
        return
    kit = kit_of_assignment(record["assignment"], record["nodeId"])
    if kit is None or not store.applied(db, event_id, event):
        return
    enrolled = store.enroll(db, record, kit, event["at"])
    scope = record["project"], record["workspace"], record["executionId"]
    if enrolled:
        for tier in ("reported", "verified"):
            store.outcome(db, scope, tier, "unknown", event_id, "awaiting-outcome", event["at"])
    if event["kind"] == "result.reported":
        store.outcome(db, scope, "reported", _reported(db, record, event), event_id, "agent-step-report", event["at"])
    elif event["actor"]["kind"] == "human" and event["data"].get("decision") == "close_card":
        closed = _closed(db, record, event)
        changed = store.outcome(db, scope, "verified", "pass" if closed else "unknown", event_id,
                                "human-closed-merged-run" if closed else "human-close-not-attributable", event["at"])
        if changed:
            harness_memory.enqueue(db, scope, event_id, "pass" if closed else "unknown", event["at"])
