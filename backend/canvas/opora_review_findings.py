"""Resolution of posted findings and the human decision at the round cap (docs/oporahub-review-jobs.md).

Every finding ends `fixed` (confirmed by voters in a later round) or `resolved` with a reason.
An important finding is resolved only by a human session; an agent may resolve nit and
pre_existing findings with a reason. After the round cap only a human accepts an unreviewed head."""
from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_review_job_validation import reason
from backend.canvas.opora_review_jobs import capped
from database.repositories.opora_execution_pull_requests import ExecutionPullRequests
from database.repositories.opora_review_jobs import public_finding


class FindingMissing(LookupError):
    """Unknown finding in this scope (HTTP 404)."""


class HumanRequired(PermissionError):
    """Only an identified human session may do this (HTTP 403)."""


class ReviewFindings:
    def __init__(self, jobs):
        self.jobs = jobs

    def resolve(self, finding_id, payload, actor):
        project, workspace, text = reason(payload)
        with self.jobs.transaction(project, workspace) as store:
            row = store.finding(finding_id)
            if row is None:
                raise FindingMissing("Unknown review finding.")
            if row["status"] != "open":
                resolution = row["resolution"] or {}
                if resolution.get("kind") == "resolved" and resolution.get("reason") == text:
                    return public_finding(row)
                raise ValueError("Finding is already closed.")
            if actor != "human" and row["severity"] == "important":
                raise HumanRequired("Only a human resolves an important finding without a fix.")
            row = store.update_finding(finding_id, status="resolved", updated_at=stamp(), resolution={
                "kind": "resolved", "by": actor, "reason": text, "at": stamp()})
            return public_finding(row)

    def decide(self, payload, actor):
        """Human accepts a head that the capped automatic review will not cover."""
        if actor != "human":
            raise HumanRequired("Only a human decides after the review round cap.")
        project, workspace, text = reason(payload, ("repository", "number", "headSha"))
        config = self.jobs.config()
        repository = payload["repository"].casefold() if isinstance(payload["repository"], str) else None
        with self.jobs.transaction(project, workspace) as store:
            links = ExecutionPullRequests(store.db, project, workspace).listing()
            link = next((item for item in links if (item["repository"], item["number"], item["head_sha"])
                         == (repository, payload["number"], payload["headSha"])), None)
            if link is None:
                raise ValueError("No linked pull request has this head.")
            jobs = store.jobs_for_pr(repository, payload["number"])
            live = any(job["head_sha"] == payload["headSha"] and job["phase"] != "superseded" for job in jobs)
            if live or not capped(jobs, config):
                raise ValueError("This head is still covered by automatic review.")
            store.insert_decision(repository, payload["number"], payload["headSha"], "accept_unreviewed_head",
                                  text, actor, stamp())
            return store.decision(repository, payload["number"], payload["headSha"])
