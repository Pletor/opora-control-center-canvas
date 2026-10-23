"""Read-only merge gate per linked PR (docs/oporahub-review-jobs.md, "Brána merge").

`reviewGate = {status: pending|blocked|ready, openImportant, requiredHumanApprovals,
humanApprovalsAtHead, reasons[]}`. Human approvals come only from stored GitHub evidence of
the exact current head SHA (reusing the evidence review rules: User accounts with write
permission, not the PR author); configured agent accounts never count. Nothing is written."""
from backend.canvas import opora_design_preview as design_preview
from backend.canvas import opora_review_gate_rules as gate_rules
from backend.canvas import opora_review_humans as review_humans
from backend.canvas import opora_review_lens as review_lens
from backend.canvas import opora_review_step_evidence as step_evidence
from backend.canvas.opora_review_jobs import capped
from backend.canvas.opora_review_status import _reviews
from database.repositories.opora_execution_pull_requests import ExecutionPullRequests
from database.repositories.opora_review_evidence import ReviewEvidenceRepository
from database.repositories.opora_review_jobs import ReviewJobs

BLOCKING = ("review_round_cap_reached", "open_important_findings", "changes_requested", "invalid_review_evidence",
            *gate_rules.BLOCKING)


def human_approvals(evidence, repository, number, head, agent_ids):
    """(approvals at head, changes requested, reasons) from the newest complete snapshot of this head."""
    if evidence is None:
        return 0, False, ["invalid_review_evidence"]
    newest_any = None
    for snapshot in evidence:
        if snapshot.get("prNumber") != number or str((snapshot.get("repository") or {}).get("fullName", "")).casefold() != repository:
            continue
        newest_any = newest_any or snapshot
        if snapshot.get("complete") is not True or (snapshot.get("pr") or {}).get("headSha") != head:
            continue
        reviews, invalid = _reviews(snapshot, head)
        if invalid:
            return 0, False, ["invalid_review_evidence"]
        reviews = [review for review in reviews if review["userId"] not in agent_ids]
        approvals = {review["userId"] for review in reviews if review["state"] == "APPROVED" and review["commitId"] == head}
        return len(approvals), any(review["state"] == "CHANGES_REQUESTED" for review in reviews), []
    return 0, False, ["github_evidence_stale_head" if newest_any else "github_evidence_missing"]


def gate(store, link, evidence, config, now=None):
    repository, number, head = link["repository"], link["number"], link["head_sha"]
    jobs = store.jobs_for_pr(repository, number)
    job = next((item for item in jobs if item["head_sha"] == head and item["phase"] != "superseded"), None)
    reasons = []
    if job is None:
        if not capped(jobs, config):
            reasons.append("review_not_enqueued")
        elif store.decision(repository, number, head) is None:
            reasons.append("review_round_cap_reached")
    elif job["phase"] != "completed":
        reasons.append("review_in_progress")
    # Without a tier for this head the gate fails closed to the high tier requirement.
    required = job["required_approvals"] if job else config["approvals"]["high"]
    findings = store.findings_for_pr(repository, number)
    important = sum(item["severity"] == "important" and item["status"] == "open" for item in findings)
    if important:
        reasons.append("open_important_findings")
    approvals, rejected, notes = human_approvals(evidence, repository, number, head, set(config["agentAccountIds"]))
    # Verified-identity registry in use: count distinct people, director included (opora_review_humans).
    humans = review_humans.count(store.db, *store.scope, link, evidence, config["agentAccountIds"])
    approvals = approvals if humans is None else humans["count"]
    if rejected:
        reasons.append("changes_requested")
    if approvals < required:
        reasons += ["human_approvals_missing", *notes]
    elif "invalid_review_evidence" in notes:
        reasons.append("invalid_review_evidence")
    extra, readiness = gate_rules.evaluate(store, link, evidence, config, now)  # security, self-checks, queue
    reasons += extra
    status = ("blocked" if any(reason in BLOCKING for reason in reasons) else "pending" if reasons else "ready")
    result = {"executionId": link["execution_id"], "cardId": link["node_id"], "repository": repository,
            "number": number, "headSha": head, "prState": link["state"],
            "reviewJobId": job["job_id"] if job else None, "round": job["round"] if job else None,
            "riskTier": job["risk_tier"] if job else None, "mergeReadiness": readiness,
            "reviewGate": {"status": status, "openImportant": important, "requiredHumanApprovals": required,
                           "humanApprovalsAtHead": approvals, "reasons": reasons}}
    if humans is not None:
        result["reviewGate"]["humans"] = humans
    if lens := review_lens.for_link(store.db, *store.scope, link):  # optional evidence, never a reason
        result["evidence"] = {"review": {"lens": lens}}
    if shots := design_preview.for_link(store.db, *store.scope, link):  # screenshots + human look, never a reason
        result.setdefault("evidence", {})["preview"] = shots
    if steps := step_evidence.for_link(store.db, *store.scope, link):  # per plan step, never a reason
        result.setdefault("evidence", {})["steps"] = steps
    return result


def review_gates(db, project, workspace, config, now=None):
    """Gates for every linked PR; callers hold the project locks (read-only, no transaction)."""
    store = ReviewJobs(db, project, workspace)
    links = ExecutionPullRequests(db, project, workspace).listing()
    evidence = []
    if links:
        try:
            evidence = ReviewEvidenceRepository(db, project, workspace).list(100)
        except ValueError:
            evidence = None  # Corrupt stored evidence never yields approvals.
    return sorted((gate(store, link, evidence, config, now) for link in links),
                  key=lambda item: (item["repository"], item["number"], item["executionId"]))


def read_review_gates(canvas, project, workspace, config=None):
    """Public read function: None when automated review is disabled, otherwise the gate list."""
    from backend.canvas import opora_review_risk as risk
    from backend.canvas.opora_execution_validation import validate
    validate({"project": project, "workspace": workspace}, set())
    config = config if config is not None else risk.load()
    if not config["enabled"]:
        return None
    with canvas.graph_lock_for(project), canvas.lock_for(project):
        return review_gates(canvas.db_for(project), project, workspace, config)
