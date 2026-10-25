"""Exact-version native closure evidence; no self-report or inferred invocation credit."""
from backend.canvas.graph import digest

TABLES = {"harness_learning_runs", "harness_learning_resources", "harness_learning_problems",
          "harness_learning_outcomes", "harness_learning_sources", "opora_events",
          "desktop_v3_state", "opora_execution_pull_requests"}
LIMIT = 10000


def read(db, project, workspace, resource, problem):
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not TABLES <= tables:
        return None
    version = digest({key: resource[key] for key in ("resource", "category", "digest", "requires")})
    rows = db.execute("""
      SELECT r.execution_id,r.node_id,o.source_event,
        CASE WHEN o.outcome='pass' AND o.reason='human-closed-merged-run'
          AND EXISTS(SELECT 1 FROM harness_learning_sources s JOIN opora_events e ON e.id=s.event_id
            WHERE s.project_id=r.project_id AND s.workspace_id=r.workspace_id
            AND s.event_id=o.source_event AND s.kind='decision.resolved'
            AND e.project_id=r.project_id AND e.workspace_id=r.workspace_id AND e.node_id=r.node_id
            AND e.execution_id=r.execution_id AND e.kind='decision.resolved' AND e.actor_kind='human'
            AND e.source IS NULL AND json_extract(e.data,'$.decision')='close_card')
          AND EXISTS(SELECT 1 FROM desktop_v3_state d,json_each(d.state,'$.nodes') n
            WHERE d.project_id=r.project_id AND d.workspace_id=r.workspace_id AND n.key=r.node_id
            AND json_extract(n.value,'$.done.confirmed')=1)
          AND (SELECT COUNT(*) FROM opora_execution_pull_requests x WHERE x.project_id=r.project_id
            AND x.workspace_id=r.workspace_id AND x.execution_id=r.execution_id AND x.node_id=r.node_id
            AND x.accepted_revision=r.accepted_revision AND x.state='merged'
            AND x.merge_sha IS NOT NULL AND x.merge_sha<>'')=1
        THEN 1 ELSE 0 END AS confirmed
      FROM harness_learning_runs r
      JOIN harness_learning_resources v USING(project_id,workspace_id,execution_id)
      JOIN harness_learning_problems p USING(project_id,workspace_id,execution_id)
      LEFT JOIN harness_learning_outcomes o ON o.project_id=r.project_id AND o.workspace_id=r.workspace_id
        AND o.execution_id=r.execution_id AND o.tier='verified'
      WHERE r.project_id=? AND r.workspace_id=? AND v.resource_id=? AND v.content_digest=?
        AND v.version_digest=? AND v.category=? AND p.problem=?
      ORDER BY r.execution_id LIMIT ?
    """, (project, workspace, resource["resource"], resource["digest"], version,
          resource["category"], problem, LIMIT + 1)).fetchall()
    if len(rows) > LIMIT or len({r[0] for r in rows}) != len(rows):
        return None  # Never truncate a denominator or pool ambiguous enrollment.
    passed = sum(row[3] for row in rows)
    return {"versionDigest": version, "executions": len(rows), "verifiedPasses": passed,
            "unknown": len(rows) - passed, "verifiedCards": len({r[1] for r in rows if r[3]}),
            "coverage": passed / len(rows) if rows else None,
            "sourceDigest": digest([list(row) for row in rows])}
