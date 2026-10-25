"""Transactional immutable memory facts and lease-fenced, idempotent delivery bookkeeping."""
import json
import uuid

KEY = "project_id=? AND workspace_id=? AND execution_id=? AND source_event=? AND resource_id=?"


def enqueue(db, scope, event_id, outcome, at):
    if outcome != "pass" and not db.execute(
        "SELECT 1 FROM harness_memory_deliveries WHERE project_id=? AND workspace_id=? AND execution_id=? "
        "AND json_extract(payload, '$.schema')='harness.memory/1' LIMIT 1", scope
    ).fetchone():
        return
    run = db.execute("SELECT node_id,assignment_digest,accepted_revision,kit_digest FROM harness_learning_runs"
                     " WHERE project_id=? AND workspace_id=? AND execution_id=?", scope).fetchone()
    problems = [row[0] for row in db.execute("SELECT problem FROM harness_learning_problems"
                " WHERE project_id=? AND workspace_id=? AND execution_id=? ORDER BY problem", scope)]
    resources = db.execute("SELECT resource_id,content_digest,version_digest,category FROM harness_learning_resources"
                           " WHERE project_id=? AND workspace_id=? AND execution_id=? ORDER BY resource_id", scope)
    for resource in resources:
        payload = {"schema": "harness.memory/1", "project": scope[0], "workspace": scope[1], "executionId": scope[2],
                   "nodeId": run[0], "assignmentDigest": run[1], "acceptedRevision": run[2], "kitDigest": run[3],
                   "resource": {"id": resource[0], "contentDigest": resource[1], "versionDigest": resource[2], "category": resource[3]},
                   "problems": problems, "sourceEvent": event_id, "at": at, "outcome": outcome,
                   "meaning": "Historical selected-kit association; invocation and causal benefit unobserved."
                              " Check current native Harness outcomes before reuse; unknown withdraws earlier closure."}
        db.execute("INSERT OR IGNORE INTO harness_memory_deliveries VALUES(?,?,?,?,?,?,?,'pending',0,0,'',0,'','','')",
                   (*scope, event_id, resource[0], run[0], json.dumps(payload, ensure_ascii=False, sort_keys=True)))


def claim(db, project, now):
    condition = "((state IN ('pending','retry','waiting-role') AND next_attempt<=?) OR (state='working' AND lease_until<=?))"
    row = db.execute("SELECT project_id,workspace_id,execution_id,source_event,resource_id FROM harness_memory_deliveries"
                     " WHERE project_id=? AND " + condition + " ORDER BY source_event,resource_id LIMIT 1", (project, now, now)).fetchone()
    if row is None:
        return None
    key, owner = tuple(row), uuid.uuid4().hex
    changed = db.execute("UPDATE harness_memory_deliveries SET state='working',attempts=attempts+1,lease_owner=?,lease_until=?"
                         " WHERE " + KEY + " AND " + condition, (owner, now + 300, *key, now, now)).rowcount
    if not changed:
        return None
    value = db.execute("SELECT node_id,payload,attempts,role_id FROM harness_memory_deliveries WHERE " + KEY, key).fetchone()
    return {"key": key, "owner": owner, "node": value[0], "payload": value[1], "attempts": value[2], "role": value[3]}


def current(db, job):
    try:
        schema = json.loads(job["payload"]).get("schema")
    except (ValueError, AttributeError):
        return False
    if schema == "harness.fixture-memory/1":
        from database.repositories.harness_fixture_memory import current as fixture_current
        return fixture_current(db, job)
    if schema == "harness.shared-memory/1":
        from backend.library.harness_shared_memory import valid_job
        return valid_job(db, job)
    if schema != "harness.memory/1":
        return False
    row = db.execute("SELECT source_event FROM harness_learning_outcomes WHERE project_id=? AND workspace_id=?"
                     " AND execution_id=? AND tier='verified'", job["key"][:3]).fetchone()
    return row is not None and row[0] == job["key"][3]


def role(db, job):
    if job["role"]:
        return job["role"]
    row = db.execute("SELECT state FROM desktop_v3_state WHERE project_id=? AND workspace_id=?", job["key"][:2]).fetchone()
    if row:
        try:
            return json.loads(row[0]).get("nodes", {}).get(job["node"], {}).get("agentRole", "")
        except (ValueError, AttributeError):
            pass
    return ""


def finish(db, job, state, now, *, error="", role="", uri=""):
    delay = min(3600, 2 ** min(job["attempts"], 11)) if state == "retry" else 60
    return db.execute("UPDATE harness_memory_deliveries SET state=?,next_attempt=?,lease_owner='',lease_until=0,"
                      "role_id=?,uri=?,error=? WHERE " + KEY + " AND lease_owner=?",
                      (state, now + delay, role, uri, error, *job["key"], job["owner"])).rowcount


def status(db, project, workspace, limit=100):
    rows = db.execute("SELECT execution_id,source_event,resource_id,state,attempts,error,uri,next_attempt,lease_until FROM harness_memory_deliveries"
                      " WHERE project_id=? AND workspace_id=? ORDER BY source_event DESC,resource_id LIMIT ?",
                      (project, workspace, limit + 1)).fetchall()
    return {"schema": "harness.memory-delivery/1", "limited": len(rows) > limit,
            "meaning": "submitted is a content-write acknowledgment, not completed indexing or verified memory extraction",
            "items": [dict(zip(("executionId", "sourceEvent", "resource", "state", "attempts", "error", "uri", "nextAttempt", "leaseUntil"), row)) for row in rows[:limit]]}
