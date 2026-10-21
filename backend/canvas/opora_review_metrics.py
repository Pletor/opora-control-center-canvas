"""Deterministic review metrics over stored review jobs, findings, GitHub evidence, reverts and incidents.

Contract: docs/oporahub-review-identity.md ("Metriky"). The point is human time per PR with
revert and incident rates as guardrails, and review noise measured by author responses
(fixed vs resolved without a fix) plus findings the voters rejected. Read-only; same stored
state and `now` always give the same document."""
import json
import re
import statistics
import time
from datetime import datetime

from backend.canvas import opora_review_risk as risk
from backend.canvas.opora_review_humans import approvers
from backend.canvas.opora_review_insight_common import project_id, reading, workspace_id
from backend.canvas.opora_review_status import _reviews
from database.repositories.opora_review_evidence import ReviewEvidenceRepository

WINDOW = re.compile(r"([1-9][0-9]{0,2})d")
SEVERITIES = ("important", "nit", "pre_existing")
PR_LIMIT = 200


def window_seconds(value):
    if value in (None, "all"):
        return None
    match = WINDOW.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        raise ValueError("window musí být 'all' nebo '<1–999>d'.")
    return int(match.group(1)) * 86400


def epoch(value):
    try:
        parsed = datetime.fromisoformat(str(value))
        return parsed.timestamp() if parsed.tzinfo else None
    except ValueError:
        return None


def rate(part, whole):
    return None if not whole else round(part / whole, 4)


def _rows(db, sql, parameters):
    return db.execute(sql, parameters).fetchall()


def collect(db, project, workspace):
    """{(repository, number): pr facts} for every PR with at least one review job.

    Rounds and voter rejections count only `kind='code'` jobs; security review rounds are
    reported separately as `securityRounds` (docs/oporahub-review-jobs.md, "Bezpečnostní review")."""
    where, parameters = " WHERE project_id=?" + (" AND workspace_id=?" if workspace else ""), (
        (project, workspace) if workspace else (project,))
    prs = {}
    for ws, repo, number, phase, created, candidates, kind in _rows(
            db, "SELECT workspace_id,repository,number,phase,created_at,candidates,kind FROM opora_review_jobs" + where
            + " ORDER BY created_at,job_id", parameters):
        pr = prs.setdefault((repo, number), {"workspace": ws, "repository": repo, "number": number, "start": created,
                                             "rounds": 0, "securityRounds": 0, "findings": [], "rejected": 0,
                                             "decisions": []})
        if phase == "completed" and kind != "code":
            pr["securityRounds"] += 1
        elif phase == "completed":
            pr["rounds"] += 1
            pr["rejected"] += sum(item.get("kind") == "finding" and item.get("accepted") is False
                                  for item in json.loads(candidates))
    for repo, number, severity, status in _rows(
            db, "SELECT repository,number,severity,status FROM opora_review_findings" + where, parameters):
        if (repo, number) in prs:
            prs[(repo, number)]["findings"].append((severity, status))
    for repo, number, created in _rows(db, "SELECT repository,number,created_at FROM opora_review_decisions" + where,
                                       parameters):
        if (repo, number) in prs:
            prs[(repo, number)]["decisions"].append(created)
    return prs


def human_facts(evidence, pr, agent_ids):
    """(approvals at the newest observed head, earliest human decision time) from stored snapshots."""
    approvals, earliest = None, [epoch(value) for value in pr["decisions"]]
    for snapshot in evidence:
        if (snapshot.get("prNumber") != pr["number"] or snapshot.get("complete") is not True
                or str((snapshot.get("repository") or {}).get("fullName", "")).casefold() != pr["repository"]):
            continue
        head = (snapshot.get("pr") or {}).get("headSha")
        if approvals is None:  # Newest complete snapshot of this PR decides the approval count.
            approvals = len(approvers([snapshot], pr["repository"], pr["number"], head, agent_ids))
        reviews, _ = _reviews(snapshot, head)
        earliest += [epoch(item["submittedAt"]) for item in reviews if item["userId"] not in agent_ids
                     and item["state"] in ("APPROVED", "CHANGES_REQUESTED")]
    times = [value for value in earliest if value is not None]
    start = epoch(pr["start"])
    return approvals or 0, (max(0.0, min(times) - start) if times and start is not None else None)


def compute(db, project, workspace, window, now, agent_ids, insights):
    seconds = window_seconds(window)
    since = None if seconds is None else now - seconds
    prs = {key: value for key, value in collect(db, project, workspace).items()
           if since is None or (epoch(value["start"]) or 0) >= since}
    evidence = {}
    reverted = {(item["repository"], item["number"]) for item in insights.reverts()}
    incidents = [item for item in insights.incidents() if (item["repository"], item["number"]) in prs]
    rows = []
    for key in sorted(prs):
        pr = prs[key]
        if pr["workspace"] not in evidence:
            try:
                evidence[pr["workspace"]] = ReviewEvidenceRepository(db, project, pr["workspace"]).list(100)
            except ValueError:
                evidence[pr["workspace"]] = []  # Corrupt evidence never yields approvals.
        approvals, decision = human_facts(evidence[pr["workspace"]], pr, set(agent_ids))
        rows.append({"repository": pr["repository"], "number": pr["number"], "rounds": pr["rounds"],
                     "securityRounds": pr["securityRounds"], "findings": len(pr["findings"]), "humanApprovals": approvals,
                     "timeToHumanDecisionSeconds": decision, "reverted": key in reverted,
                     "incidents": sum((item["repository"], item["number"]) == key for item in incidents),
                     "_findings": pr["findings"], "_rejected": pr["rejected"]})
    findings = [item for row in rows for item in row.pop("_findings")]
    rejected = sum(row.pop("_rejected") for row in rows)
    fixed = sum(status == "fixed" for _, status in findings)
    resolved = sum(status == "resolved" for _, status in findings)
    decisions = [row["timeToHumanDecisionSeconds"] for row in rows if row["timeToHumanDecisionSeconds"] is not None]
    count = len(rows)
    return {"projectId": project, "workspaceId": workspace, "window": window, "since": since, "now": now,
            "prsReviewed": count,
            "findingsBySeverity": {severity: sum(item == severity for item, _ in findings) for severity in SEVERITIES},
            "findingOutcomes": {"fixed": fixed, "resolvedWithoutFix": resolved, "rejectedByVoters": rejected,
                                "open": sum(status == "open" for _, status in findings)},
            "findingAcceptanceRate": rate(fixed, fixed + resolved),
            "voterRejectionRate": rate(rejected, rejected + len(findings)),
            "roundsPerPr": {"mean": rate(sum(row["rounds"] for row in rows), count),
                            "max": max((row["rounds"] for row in rows), default=0)},
            "securityRounds": {"mean": rate(sum(row["securityRounds"] for row in rows), count),
                               "max": max((row["securityRounds"] for row in rows), default=0)},
            "humanApprovalsPerPr": rate(sum(row["humanApprovals"] for row in rows), count),
            "timeToHumanDecisionSeconds": {"samples": len(decisions),
                                           "median": statistics.median(decisions) if decisions else None,
                                           "mean": round(statistics.fmean(decisions), 1) if decisions else None},
            "guardrails": {"revertRate": rate(sum(row["reverted"] for row in rows), count),
                           "incidentRate": rate(sum(row["incidents"] > 0 for row in rows), count)},
            "incidents": incidents, "prs": rows[:PR_LIMIT], "truncated": count > PR_LIMIT}


def read_review_metrics(canvas, project, workspace=None, window="30d", now=None, config=None):
    project, workspace = project_id(project), workspace_id(workspace, nullable=True)
    window_seconds(window)
    agent_ids = (config if config is not None else risk.load())["agentAccountIds"]
    with reading(canvas, project) as (db, insights):
        return compute(db, project, workspace, window or "all", time.time() if now is None else now, agent_ids, insights)
