"""Security review as its own blocking job kind (docs/oporahub-review-jobs.md, "Bezpečnostní review").

A `kind: "security"` job uses the same finder/voter slots, leases, aggregation and findings as
the code review job; only `job.kind` tells the worker to use its security prompt. It is enqueued
for every head whose change touches a security-sensitive path, whose risk tier reaches
`min_tier`, or whose PR still has an open security finding (so a later round can confirm the
fix). Other heads get a `not_required` marker so the decision is taken once per head. Open
`important` security findings block the gate until voters confirm a fix on a later head or a
human resolves them with a reason. Security rounds have no round cap."""
from backend.canvas import opora_review_risk as risk
from backend.canvas.opora_review_gate_config import rules

KIND = "security"
LIVE = ("find", "vote")


def _live(jobs, head):
    return next((job for job in jobs if job["head_sha"] == head and job["phase"] != "superseded"), None)


def security_findings(store, repository, number):
    """Findings raised by security jobs of this PR (any status)."""
    ids = {job["job_id"] for job in store.jobs_for_pr(repository, number, KIND)}
    return [item for item in store.findings_for_pr(repository, number) if item["job_id"] in ids]


def due(store, link, config):
    """The head has no security decision yet (job or `not_required` marker)."""
    if not rules(config)["security"]["enabled"]:
        return False
    return _live(store.jobs_for_pr(link["repository"], link["number"], KIND), link["head_sha"]) is None


def reasons_for(store, link, change, config):
    """Why this head needs a security review; empty means not required."""
    setting = rules(config)["security"]
    tier = risk.classify(change, config)
    reasons = []
    if risk.TIERS.index(tier["tier"]) >= risk.TIERS.index(setting["minTier"]):
        reasons.append("risk_tier:" + tier["tier"])
    if change is not None and change.get("complete") is True:
        globs = setting["paths"] or config["sensitive"]
        reasons += ["security_path:" + glob for glob in sorted(
            {glob for glob in globs for item in change["files"] if risk.matches(glob, item["path"])})]
    if any(item["status"] == "open" for item in security_findings(store, link["repository"], link["number"])):
        reasons.append("open_security_findings")
    return reasons


def enqueue_security(store, link, change, config, now):
    """Decide once per head; returns the created security job IDs (empty for a marker or no-op)."""
    from backend.canvas.opora_review_jobs import enqueue
    if not due(store, link, config):
        return []
    reasons = reasons_for(store, link, change, config)
    job_id = enqueue(store, link, change, config, now, kind=KIND)
    if job_id is None:
        return []
    job = store.job(job_id)
    if reasons:
        store.update_job(job_id, risk={**job["risk"], "securityReasons": reasons})
        return [job_id]
    for task in store.tasks(job_id):
        if task["state"] in ("open", "claimed"):
            store.update_task(task["task_id"], state="superseded", owner=None, token=None, expires_at=None)
    store.update_job(job_id, phase="not_required", risk={**job["risk"], "securityReasons": []}, updated_at=now,
                     completed_at=now)
    return []


def evaluate(store, link, config):
    """(reasons, details) of the security rule for the link's current head."""
    if not rules(config)["security"]["enabled"]:
        return [], None
    repository, number = link["repository"], link["number"]
    job = _live(store.jobs_for_pr(repository, number, KIND), link["head_sha"])
    reasons = []
    if job is None:
        reasons.append("security_review_not_enqueued")
    elif job["phase"] in LIVE:
        reasons.append("security_review_in_progress")
    blocking = [item for item in security_findings(store, repository, number)
                if item["status"] == "open" and item["severity"] == "important"]
    if blocking:
        reasons.append("open_security_findings")
    return reasons, {"reviewJobId": job["job_id"] if job else None, "phase": job["phase"] if job else None,
                     "reasons": (job["risk"] or {}).get("securityReasons", []) if job else [],
                     "openImportant": len(blocking)}
