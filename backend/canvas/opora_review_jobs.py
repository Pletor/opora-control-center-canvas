"""Deterministic enqueue of automated code review jobs per execution PR head (docs/oporahub-review-jobs.md).

The backend does all bookkeeping: one job per (PR, headSha), monotonic rounds with a cap,
incremental `sinceSha`, a risk tier derived from the change and fixed finder slots. GitHub is
only read (changed files, outside every lock); nothing here posts to GitHub."""
import time
from contextlib import contextmanager

from backend.canvas import opora_review_merge_queue as merge_queue
from backend.canvas import opora_review_risk as risk
from backend.canvas import opora_review_security as security
from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_execution_validation import validate
from backend.canvas.opora_executions import OporaExecutions
from backend.canvas.opora_review_aggregation import short_id
from database.repositories.opora_execution_pull_requests import ExecutionPullRequests
from database.repositories.opora_review_jobs import ReviewJobs, public_finding, public_job

ACTIVE = ("find", "vote")


class ReviewJobsDisabled(LookupError):
    """Automated review is switched off in the review job config (HTTP 409 `review_jobs_disabled`)."""


def carried(job):
    """A job that took over a completed review because a rebase left the change content unchanged."""
    return bool((job.get("risk") or {}).get("carriedFrom"))


def completed_rounds(jobs):
    """Reviewed rounds; carried jobs are no new round."""
    return [job for job in jobs if job["phase"] == "completed" and not carried(job)]


def capped(jobs, config):
    """No further automatic round: the human decides about newer heads."""
    return len(completed_rounds(jobs)) >= config["maxRounds"]


def carry_source(jobs):
    """The newest reviewed (completed, not carried) round, whose content a rebased head may match."""
    done = completed_rounds(jobs)
    return done[-1] if done else None


def needs_job(jobs, link, config):
    """The head has no live job. A capped PR still qualifies: its head may carry the last review over."""
    if any(job["head_sha"] == link["head_sha"] and job["phase"] != "superseded" for job in jobs):
        return False
    return not capped(jobs, config) or carry_source(jobs) is not None


def fingerprint_of(job):
    return (job.get("risk") or {}).get("patchFingerprint")


def needs_fingerprint(jobs):
    """(base, head) of the carry source when its fingerprint is not stored yet (jobs from before PIPE-006)."""
    source = carry_source(jobs)
    if source is None or fingerprint_of(source) or not source.get("base_sha"):
        return None
    return source["base_sha"], source["head_sha"]


def remember_fingerprint(store, jobs, fingerprint, now):
    """Store a fingerprint computed for an older source job once, so the compare read is not repeated."""
    source = carry_source(jobs)
    if fingerprint and source is not None and not fingerprint_of(source):
        store.update_job(source["job_id"], risk={**(source["risk"] or {}), "patchFingerprint": fingerprint},
                         updated_at=now)


def _supersede_active(store, prior, now):
    for job in prior:
        if job["phase"] in ACTIVE:  # A newer push makes an unfinished review of an older head moot.
            store.update_job(job["job_id"], phase="superseded", updated_at=now)
            for task in store.tasks(job["job_id"]):
                if task["state"] in ("open", "claimed"):
                    store.update_task(task["task_id"], state="superseded", expires_at=None)


def carry(store, link, change, source, existing, fingerprint, now):
    """Same content as the reviewed source round: a completed job without finders, in the source's round."""
    fields = {"phase": "completed", "round": source["round"], "since_sha": source["head_sha"],
              "risk_tier": source["risk_tier"], "required_approvals": source["required_approvals"],
              "risk": {**(source["risk"] or {}), "carriedFrom": source["job_id"], "patchFingerprint": fingerprint},
              "completed_at": now, "updated_at": now}
    if existing is not None:  # A superseded job of this head: its slots must not come back.
        for task in store.tasks(existing["job_id"]):
            if task["state"] in ("open", "claimed"):
                store.update_task(task["task_id"], state="superseded", expires_at=None)
        store.update_job(existing["job_id"], **fields)
        return existing["job_id"]
    repository, number, head = link["repository"], link["number"], link["head_sha"]
    job_id = short_id("rj_", *store.scope, repository, number, head)
    store.insert_job({
        "job_id": job_id, "execution_id": link["execution_id"], "node_id": link["node_id"],
        "repository": repository, "number": number, "base_sha": (change or {}).get("baseSha"), "head_sha": head,
        "finders": source["finders"], "voters": source["voters"], "required_votes": source["required_votes"],
        "candidates": [], "created_at": now, "kind": "code", **fields})
    return job_id


def enqueue(store, link, change, config, now, kind="code"):
    """Insert the job for the link's current head once; returns the job ID or None (exists or capped).

    A code head whose change fingerprint equals the last reviewed round's gets a carried job instead
    (PIPE-006): completed, same round, no finders, also past the round cap.
    `kind="security"` is a separate round sequence without the round cap (opora_review_security)."""
    repository, number, head = link["repository"], link["number"], link["head_sha"]
    prior = store.jobs_for_pr(repository, number, kind)
    existing = next((job for job in prior if job["head_sha"] == head), None)
    if existing is not None and existing["phase"] != "superseded":
        return None
    fingerprint = (change or {}).get("fingerprint") if kind == "code" and (change or {}).get("complete") else None
    source = carry_source(prior) if fingerprint else None
    if source is not None and source["head_sha"] != head and fingerprint_of(source) == fingerprint:
        _supersede_active(store, prior, now)  # Checked before the cap: a clean rebase is no new round.
        return carry(store, link, change, source, existing, fingerprint, now)
    if kind == "code" and capped(prior, config):
        return None
    _supersede_active(store, prior, now)
    done = completed_rounds(prior)
    # A carried head has the reviewed content on the newer base, so the next diff starts there.
    finished = [job for job in prior if job["phase"] == "completed"]
    since = finished[-1]["head_sha"] if finished else None
    if existing is not None:
        return revive(store, existing, len(done) + 1, since, now)
    tier = risk.classify(change, config)
    if fingerprint:
        tier = {**tier, "patchFingerprint": fingerprint}
    job_id = short_id("rj_", *store.scope, repository, number, head, *([kind] if kind != "code" else []))
    store.insert_job({
        "job_id": job_id, "execution_id": link["execution_id"], "node_id": link["node_id"],
        "repository": repository, "number": number, "base_sha": (change or {}).get("baseSha"), "head_sha": head,
        "round": len(done) + 1, "since_sha": since, "risk_tier": tier["tier"],
        "risk": tier, "required_approvals": tier["requiredApprovals"], "finders": config["finders"],
        "voters": config["voters"], "required_votes": config["requiredVotes"], "phase": "find", "candidates": [],
        "created_at": now, "updated_at": now, "completed_at": None, "kind": kind})
    for slot in range(1, config["finders"] + 1):
        store.insert_task({"task_id": f"{job_id}-finder-{slot}", "job_id": job_id, "role": "finder", "slot": slot,
                           "state": "open", "epoch": 0})
    return job_id


def revive(store, job, round_number, since, now):
    """A force-push back to a previously superseded head resumes that job; submitted slots stay valid."""
    tasks = store.tasks(job["job_id"])
    for task in tasks:
        if task["state"] == "superseded":
            store.update_task(task["task_id"], state="open", owner=None, token=None, expires_at=None)
    phase = "vote" if any(task["role"] == "voter" for task in tasks) else "find"
    store.update_job(job["job_id"], phase=phase, round=round_number, since_sha=since, updated_at=now)
    return job["job_id"]


class ReviewJobService:
    def __init__(self, canvas, reader=None, *, config=None, clock=time.time):
        self.canvas, self.clock, self._config, self._reader = canvas, clock, config, reader
        self.executions = OporaExecutions(canvas)

    def config(self):
        return self._config if self._config is not None else risk.load()

    def enabled(self):
        config = self.config()
        if not config["enabled"]:
            raise ReviewJobsDisabled("Automated code review is not enabled.")
        return config

    @property
    def reader(self):
        if self._reader is None:
            from backend.integrations.github_pr_change_reader import GitHubPullRequestChangeReader
            self._reader = GitHubPullRequestChangeReader()
        return self._reader

    @contextmanager
    def transaction(self, project, workspace):
        """Same lock order and BEGIN IMMEDIATE as the execution lease authority."""
        with self.executions.transaction(project, workspace) as repo:
            yield ReviewJobs(repo.db, project, workspace)

    def observe(self, link):
        if link["enrollment"] == "unavailable":  # Project without GitHub: never touch the network.
            return None
        try:
            return self.reader.change(link["repository"], link["number"], link["head_sha"])
        except Exception:  # noqa: BLE001 - any reader failure fails closed to the high tier
            return None

    def source_fingerprint(self, link, pair):
        """Fingerprint of an older reviewed head (`base...head`), read outside the locks; None on failure."""
        if pair is None or link["enrollment"] == "unavailable" or not hasattr(self.reader, "fingerprint"):
            return None
        try:
            return self.reader.fingerprint(link["repository"], *pair)
        except Exception:  # noqa: BLE001 - unknown content only disables the carry
            return None

    @staticmethod
    def _code_due(store, link, config):
        jobs = store.jobs_for_pr(link["repository"], link["number"])
        if not needs_job(jobs, link, config):
            return False, None
        # A human already decided this capped head: no carry attempt, no repeated GitHub reads.
        if capped(jobs, config) and store.decision(link["repository"], link["number"], link["head_sha"]):
            return False, None
        return True, needs_fingerprint(jobs)

    def sync(self, project, workspace):
        """Enqueue jobs for every open linked PR head without one; idempotent and safe to repeat."""
        config = self.enabled()
        validate({"project": project, "workspace": workspace}, set())
        with self.transaction(project, workspace) as store:
            due = []
            for link in ExecutionPullRequests(store.db, project, workspace).listing():
                if link["state"] != "open":
                    continue
                code, pair = self._code_due(store, link, config)
                if code or security.due(store, link, config):
                    due.append((link, pair))
        changes = [(link, self.observe(link), self.source_fingerprint(link, pair)) for link, pair in due]
        created = []
        with self.transaction(project, workspace) as store:
            links = ExecutionPullRequests(store.db, project, workspace)
            for link, change, source_fingerprint in changes:
                current = links.read(link["execution_id"])
                if current is None or current["state"] != "open" or current["head_sha"] != link["head_sha"]:
                    continue  # Head moved while reading GitHub; the next sync observes the new head.
                remember_fingerprint(store, store.jobs_for_pr(current["repository"], current["number"]),
                                     source_fingerprint, stamp())
                job_id = enqueue(store, current, change, config, stamp())
                created += [job_id] if job_id else []
                created += security.enqueue_security(store, current, change, config, stamp())
        merge_queue.observe_bases(self, project, workspace, config)
        return created

    def list(self, project, workspace):
        validate({"project": project, "workspace": workspace}, set())
        config = self.config()
        with self.transaction(project, workspace) as store:
            jobs = [public_job(job, store.tasks(job["job_id"])) for job in store.jobs()]
            findings = [public_finding(item) for item in store.findings()]
        return {"enabled": config["enabled"], "maxRounds": config["maxRounds"], "jobs": jobs, "findings": findings}
