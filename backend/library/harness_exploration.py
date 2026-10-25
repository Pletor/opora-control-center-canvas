"""Native nonproduction work-allocation limit; no new ledger or tool-quality claim."""
import os

from backend.canvas.graph import digest
from backend.canvas.opora_change_validation import scope
from backend.library.harness_scope_config import select
from backend.library.harness_verifier_records import KIND

TABLES = {"harness_learning_runs", "harness_learning_outcomes", "harness_learning_sources",
          "opora_execution_pull_requests", "opora_verification_requests", "opora_events", "desktop_v3_state"}


def policy(project, workspace):
    raw = os.environ.get("OPORA_HARNESS_EXPLORATION", "")
    if not raw:
        raise ValueError("Nonproduction exploration policy is disabled.")
    return digest(select(raw, _policy, project, workspace))


def _policy(value):
    if set(value) != {"project", "workspace", "environment"} or value["environment"] != "nonproduction":
        raise ValueError("Exploration requires an explicit nonproduction scope.")
    scope(value)
    return value


def current(db, project, workspace, expected):
    try:
        value = snapshot(db, project, workspace)
        return (value.get("policyDigest") == expected and value["status"] == "available"
                and value["admitted"] <= value["baselineCards"] // 19)
    except (ValueError, TypeError, KeyError):
        return False


def snapshot(db, project, workspace, node=None):
    result = {"schema": "harness.exploration-share/1", "maxPercent": 5, "status": "unavailable",
              "baselineCards": None, "admitted": None, "remaining": None,
              "eligible": False, "reservation": False}
    try:
        fingerprint = policy(project, workspace)
    except (ValueError, TypeError, KeyError):
        return result
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not TABLES <= tables:
        return result
    # Distinct completed cards, never claims, retries, self-reports or fixture successes.
    # A card that has ever consumed an experiment cannot also supply baseline credit.
    baseline = db.execute("""
        SELECT COUNT(DISTINCT r.node_id) FROM harness_learning_runs r
        JOIN harness_learning_outcomes o USING(project_id,workspace_id,execution_id)
        JOIN harness_learning_sources s ON s.project_id=o.project_id AND s.workspace_id=o.workspace_id
          AND s.event_id=o.source_event AND s.kind='decision.resolved'
        JOIN opora_events e ON e.id=o.source_event AND e.project_id=r.project_id
          AND e.workspace_id=r.workspace_id AND e.node_id=r.node_id AND e.execution_id=r.execution_id
          AND e.kind='decision.resolved' AND e.actor_kind='human' AND e.source IS NULL
          AND json_extract(e.data,'$.decision')='close_card'
        JOIN desktop_v3_state d ON d.project_id=r.project_id AND d.workspace_id=r.workspace_id
        JOIN json_each(d.state,'$.nodes') n ON n.key=r.node_id AND json_extract(n.value,'$.done.confirmed')=1
        JOIN opora_execution_pull_requests p ON p.project_id=r.project_id AND p.workspace_id=r.workspace_id
          AND p.execution_id=r.execution_id AND p.node_id=r.node_id AND p.accepted_revision=r.accepted_revision
        WHERE r.project_id=? AND r.workspace_id=? AND o.tier='verified' AND o.outcome='pass'
          AND o.reason='human-closed-merged-run' AND p.state='merged' AND p.merge_sha IS NOT NULL
          AND p.merge_sha<>'' AND (? IS NULL OR r.node_id<>?) AND NOT EXISTS (
            SELECT 1 FROM opora_verification_requests v WHERE v.project_id=r.project_id
              AND v.workspace_id=r.workspace_id AND v.node_id=r.node_id
              AND json_extract(v.record,'$.origin.kind')=?)
        """, (project, workspace, node, node, KIND)).fetchone()[0]
    used = db.execute("SELECT COUNT(*) FROM opora_verification_requests WHERE project_id=? AND workspace_id=? "
                      "AND json_extract(record,'$.origin.kind')=?", (project, workspace, KIND)).fetchone()[0]
    remaining = max(0, baseline // 19 - used)
    return {**result, "status": "available", "policyDigest": fingerprint, "baselineCards": baseline,
            "admitted": used, "remaining": remaining, "eligible": remaining > 0}


def admit(db, project, workspace, node):
    if not db.in_transaction:
        raise RuntimeError("Exploration admission requires the native write transaction.")
    result = snapshot(db, project, workspace, node)
    if not result["eligible"]:
        raise ValueError("Nonproduction exploration share exhausted or eligibility unavailable.")
    return result
