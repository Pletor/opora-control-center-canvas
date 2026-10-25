"""Durable exact-version fixture failures, independent of the recent-history window."""
from backend.canvas.opora_execution_validation import validate
from backend.canvas.opora_verifications import OporaVerifications

LIMIT = 1000
# Both sides of the join are scope-bound. Only native, complete observations qualify.
FAILURES = """
WITH failures AS (
 SELECT q.id AS verification_id,
        json_extract(q.record,'$.origin.problem') AS problem,
        json_extract(q.record,'$.origin.candidate.id') AS candidate,
        json_extract(q.record,'$.origin.candidate.digest') AS digest
 FROM opora_verification_requests q
 JOIN opora_verification_reports r ON r.verification_id=q.id
  AND r.project_id=q.project_id AND r.workspace_id=q.workspace_id
 WHERE q.project_id=? AND q.workspace_id=?
  AND json_extract(q.record,'$.domain')='harness-fixtures'
  AND json_extract(q.record,'$.trust')='server-pending'
  AND json_extract(q.record,'$.origin.kind')='harness-server-verifier'
  AND json_extract(q.record,'$.origin.protocol')='harness.server-fixtures/1'
  AND json_extract(q.record,'$.sourceBinding')='canvas-verified'
  AND json_type(q.record,'$.currentEligibility')='false'
  AND json_extract(r.record,'$.trust')='server-observed'
  AND json_extract(r.record,'$.sourceBinding')='canvas-verified'
  AND json_type(r.record,'$.currentEligibility')='false'
  AND json_type(r.record,'$.promotionAllowed')='false'
  AND json_type(r.record,'$.independentlyVerified')='true'
  AND json_type(r.record,'$.paired.complete')='true'
  AND json_type(r.record,'$.paired.cleanupComplete')='true'
  AND json_type(r.record,'$.authorityCurrentAtCompletion')='true'
  AND json_extract(r.record,'$.outcome')='failed'
), classified AS (
 SELECT *, COALESCE(
  typeof(problem)='text' AND instr(problem,char(0))=0 AND length(problem) BETWEEN 1 AND 200
  AND substr(problem,1,1) GLOB '[A-Za-z0-9]' AND problem NOT GLOB '*[^A-Za-z0-9_.:@/+-]*'
  AND typeof(candidate)='text' AND instr(candidate,char(0))=0 AND length(candidate) BETWEEN 1 AND 200
  AND substr(candidate,1,1) GLOB '[A-Za-z0-9]' AND candidate NOT GLOB '*[^A-Za-z0-9_.:@/+-]*'
  AND typeof(digest)='text' AND instr(digest,char(0))=0 AND length(digest)=64 AND digest NOT GLOB '*[^a-f0-9]*', 0
 ) AS bound FROM failures
)
"""


def read(canvas, project, workspace):
    """No clear/promotion mutation: changing a digest creates a distinct cohort."""
    validate({"project": project, "workspace": workspace}, set())
    with OporaVerifications(canvas).transaction(project, workspace) as repo:
        unbound = repo.db.execute(FAILURES + "SELECT COUNT(*) FROM classified WHERE NOT bound",
                                 (project, workspace)).fetchone()[0]
        rows = repo.db.execute(FAILURES + "SELECT problem,candidate,digest,MIN(verification_id) "
                               "FROM classified WHERE bound GROUP BY problem,candidate,digest "
                               "ORDER BY problem,candidate,digest LIMIT ?", (project, workspace, LIMIT + 1)).fetchall()
    return {"schema": "harness.fixture-quarantine/1", "scope": {"project": project, "workspace": workspace},
            "complete": unbound == 0 and len(rows) <= LIMIT, "unboundFailures": unbound,
            "cohorts": [{"problem": row[0], "candidate": {"id": row[1], "digest": row[2]},
                         "verificationId": row[3]} for row in rows[:LIMIT]]}
