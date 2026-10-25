"""Derived measurements only. Source adapters own authentication, evidence and transactions."""
from backend.canvas.graph import digest


def enroll(db, record, kit, at):
    scope = record["project"], record["workspace"], record["executionId"]
    inserted = db.execute("INSERT OR IGNORE INTO harness_learning_runs VALUES(?,?,?,?,?,?,?,?)",
                          (*scope, record["nodeId"], record["assignmentDigest"],
                           record["acceptedRevision"], digest(kit), at)).rowcount
    if not inserted:
        return False
    for entry in kit["resources"]:
        # Requirements/category are versioned too; identical text in another config is not pooled.
        version = digest({key: entry[key] for key in ("resource", "category", "digest", "requires")})
        db.execute("INSERT INTO harness_learning_resources VALUES(?,?,?,?,?,?,?)",
                   (*scope, entry["resource"], entry["digest"], version, entry["category"]))
    db.executemany("INSERT INTO harness_learning_problems VALUES(?,?,?,?)",
                   [(*scope, problem) for problem in kit["problems"]])
    return True


def outcome(db, scope, tier, value, event_id, reason, at):
    return db.execute("INSERT INTO harness_learning_outcomes VALUES(?,?,?,?,?,?,?,?)"
               " ON CONFLICT(project_id,workspace_id,execution_id,tier) DO UPDATE SET"
               " outcome=excluded.outcome,source_event=excluded.source_event,reason=excluded.reason,at=excluded.at"
               " WHERE excluded.source_event>harness_learning_outcomes.source_event",
               (*scope, tier, value, event_id, reason, at)).rowcount > 0


def applied(db, event_id, event):
    return db.execute("INSERT OR IGNORE INTO harness_learning_sources VALUES(?,?,?,?)",
                      (event["projectId"], event["workspaceId"], event_id, event["kind"])).rowcount == 1


def summaries(db, project, workspace, *, node=None, resource=None, limit=100):
    """Project/workspace cohorts, optionally narrowed to a card; one vote per execution/tier."""
    condition, parameters = "r.project_id=? AND r.workspace_id=?", [project, workspace]
    if node is not None:
        condition += " AND r.node_id=?"
        parameters.append(node)
    if resource is not None:
        condition += " AND v.resource_id=?"
        parameters.append(resource)
    query = ("SELECT v.resource_id,v.content_digest,v.version_digest,v.category,p.problem,o.tier,"
             "SUM(o.outcome='pass'),SUM(o.outcome='fail'),SUM(o.outcome='unknown'),COUNT(DISTINCT r.node_id),"
             "MAX(o.source_event),MIN(r.enrolled_at) FROM harness_learning_runs r"
             " JOIN harness_learning_resources v USING(project_id,workspace_id,execution_id)"
             " JOIN harness_learning_problems p USING(project_id,workspace_id,execution_id)"
             " JOIN harness_learning_outcomes o USING(project_id,workspace_id,execution_id) WHERE " + condition
             + " GROUP BY v.resource_id,v.content_digest,v.version_digest,v.category,p.problem,o.tier"
             " ORDER BY v.resource_id,v.version_digest,p.problem,o.tier LIMIT ?")
    return db.execute(query, (*parameters, limit + 1)).fetchall()
