"""Optional seam to automated code review jobs (docs/oporahub-review-jobs.md, "Stav pro agenty").

When review jobs are enabled, the agent-state `review` stage reads the merge gates of open
linked PRs and offers `review.claim` for jobs with a claimable slot; the `ai_review` gap then
disappears. Disabled (default) returns None and the previous human-only rules stay unchanged."""
from backend.canvas import opora_review_risk as risk
from backend.canvas.opora_review_gate import review_gates
from database.repositories.opora_review_jobs import ReviewJobs

_override = None


def register(config):
    """Test hook: force a review job config (or None to read the configured one)."""
    global _override  # One tiny documented registry slot, like opora_agent_state_pulls.
    _override = config


def config():
    """The review job config in force (test override first)."""
    return _override if _override is not None else risk.load()


def read(canvas, project, workspace, now):
    """`{gates, claimable}` or None when automated review is disabled. Read-only."""
    config_ = config()
    if not config_["enabled"]:
        return None
    db = canvas.db_for(project)
    gates = [item for item in review_gates(db, project, workspace, config_, now) if item["prState"] == "open"]
    store = ReviewJobs(db, project, workspace)
    claimable = {}
    for task_id in store.claimable(now):
        task = store.task(task_id)
        claimable.setdefault(task["job_id"], task["role"])
    jobs = [store.job(job_id) for job_id in sorted(claimable)]
    return {"gates": gates, "claimable": [{"reviewJobId": job["job_id"], "headSha": job["head_sha"],
                                           "role": claimable[job["job_id"]]} for job in jobs]}
