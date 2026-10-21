"""Leased finder/voter tasks: claim, heartbeat, release and submit (docs/oporahub-review-jobs.md).

The lease follows the execution pattern: a random token, a monotonic epoch per slot that never
goes back, a server TTL and request replay by (owner, requestId). Each claimed slot is meant to
run in a fresh model context. When every slot of a phase submitted, the backend advances it."""
import secrets

from backend.canvas.graph import digest
from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_execution_validation import validate
from backend.canvas.opora_executions import OporaExecutions
from backend.canvas.opora_review_aggregation import candidates, finding_id, tally
from backend.canvas.opora_review_job_validation import (
    claim_scope,
    finder_submission,
    voter_submission,
)
from database.repositories.opora_review_jobs import public_finding, public_job

PHASE = {"finder": "find", "voter": "vote"}


def _known(store, job):
    return [public_finding(item) for item in store.findings_for_pr(job["repository"], job["number"])]


def assignment(store, task, now):
    job = store.job(task["job_id"])
    value = {"reviewJobId": job["job_id"], "taskId": task["task_id"], "role": task["role"], "slot": task["slot"],
             "token": task["token"], "epoch": task["epoch"], "expiresAt": task["expires_at"], "serverNow": now,
             "job": public_job(job), "knownFindings": _known(store, job)}
    if task["role"] == "voter":
        value["candidates"] = job["candidates"]
    return {"task": value, "serverNow": now}


def advance(store, job_id, now):
    """Close the phase once every slot submitted; votes turn candidates into findings or fixes."""
    job, tasks = store.job(job_id), store.tasks(job_id)
    role = {"find": "finder", "vote": "voter"}.get(job["phase"])
    slots = [task for task in tasks if task["role"] == role]
    if role is None or not slots or any(task["state"] != "submitted" for task in slots):
        return job
    if role == "finder":
        known = {item["fingerprint"] for item in store.findings_for_pr(job["repository"], job["number"])}
        items = candidates(job_id, [(task["slot"], task["submission"]) for task in slots], known)
        if not items:
            return store.update_job(job_id, phase="completed", candidates=[], updated_at=now, completed_at=now)
        for slot in range(1, job["voters"] + 1):
            store.insert_task({"task_id": f"{job_id}-voter-{slot}", "job_id": job_id, "role": "voter", "slot": slot,
                               "state": "open", "epoch": 0})
        return store.update_job(job_id, phase="vote", candidates=items, updated_at=now)
    results = tally(job["candidates"], [task["submission"] for task in slots], job["required_votes"])
    for item in results:
        if not item["accepted"]:
            continue
        if item["kind"] == "finding":
            store.insert_finding({
                "finding_id": finding_id(job["repository"], job["number"], item["fingerprint"]),
                "repository": job["repository"], "number": job["number"], "fingerprint": item["fingerprint"],
                "job_id": job_id, "round": job["round"], "head_sha": job["head_sha"], "severity": item["severity"],
                "status": "open", "resolution": None, "created_at": now, "updated_at": now,
                "content": {key: item[key] for key in ("path", "line", "title", "rationale", "finders",
                                                       "confirms", "rejects")}})
            continue
        target = store.finding(item["findingId"])
        if target is not None and target["status"] == "open":
            store.update_finding(item["findingId"], status="fixed", updated_at=now, resolution={
                "kind": "fixed", "reviewJobId": job_id, "headSha": job["head_sha"], "confirms": item["confirms"],
                "rationale": item["rationale"]})
    return store.update_job(job_id, phase="completed", candidates=results, updated_at=now, completed_at=now)


class ReviewTasks:
    def __init__(self, jobs):
        self.jobs = jobs

    def claim(self, payload, owner):
        project, workspace, role = claim_scope(payload)
        if not isinstance(owner, str) or not owner.strip() or len(owner) > 160:
            raise ValueError("An identified review worker is required.")
        self.jobs.sync(project, workspace)
        request_digest = digest(payload)
        with self.jobs.transaction(project, workspace) as store:
            now = self.jobs.clock()
            replay = store.replay(owner, payload["requestId"])
            if replay is not None:
                task = store.task(replay[1])
                if replay[0] != request_digest or task["owner"] != owner or task["state"] not in ("claimed", "submitted"):
                    raise ValueError("Claim request identity was already used or the claim is no longer held.")
                return assignment(store, task, now)
            ready = store.claimable(now, role)
            if not ready:
                return {"task": None, "serverNow": now}
            task = store.task(ready[0])
            task = store.update_task(task["task_id"], state="claimed", owner=owner, token=secrets.token_hex(32),
                                     epoch=task["epoch"] + 1, expires_at=now + payload["ttlSeconds"])
            store.remember(owner, payload["requestId"], request_digest, task["task_id"])
            return assignment(store, task, now)

    def _held(self, store, job_id, task_id, payload, now, *, live=True):
        task = store.task(task_id)
        if task is None or task["job_id"] != job_id:
            raise ValueError("Unknown review task.")
        if task["token"] is None:
            raise ValueError("Review task credential or epoch does not match.")
        try:
            OporaExecutions.authenticate(task, payload["token"], payload["epoch"])
        except ValueError:
            raise ValueError("Review task credential or epoch does not match.") from None
        job = store.job(job_id)
        if live and (task["state"] != "claimed" or task["expires_at"] is None or task["expires_at"] <= now
                     or job["phase"] != PHASE[task["role"]]):
            raise ValueError("Review task is no longer authoritative.")
        return task, job

    def heartbeat(self, job_id, task_id, payload):
        project, workspace = validate(payload, {"token", "epoch", "ttlSeconds"})
        with self.jobs.transaction(project, workspace) as store:
            now = self.jobs.clock()
            task, _ = self._held(store, job_id, task_id, payload, now)
            task = store.update_task(task_id, expires_at=now + payload["ttlSeconds"])
            return {"reviewJobId": job_id, "taskId": task_id, "epoch": task["epoch"], "expiresAt": task["expires_at"],
                    "serverNow": now}

    def release(self, job_id, task_id, payload):
        project, workspace = validate(payload, {"token", "epoch"})
        with self.jobs.transaction(project, workspace) as store:
            now = self.jobs.clock()
            task, _ = self._held(store, job_id, task_id, payload, now, live=False)
            if task["state"] == "claimed":
                task = store.update_task(task_id, state="open", owner=None, token=None, expires_at=None)
            return {"reviewJobId": job_id, "taskId": task_id, "state": task["state"], "serverNow": now}

    def submit(self, job_id, task_id, payload):
        project, workspace = validate(payload, {"token", "epoch", "requestId", "submission"})
        submitted = digest(payload["submission"])
        with self.jobs.transaction(project, workspace) as store:
            now = self.jobs.clock()
            task, job = self._held(store, job_id, task_id, payload, now, live=False)
            if task["state"] == "submitted":
                if (task["request_id"], task["digest"]) != (payload["requestId"], submitted):
                    raise ValueError("Review task already submitted different content.")
                return self._receipt(store.job(job_id), task, now)
            task, job = self._held(store, job_id, task_id, payload, now)
            if task["role"] == "finder":
                open_ids = {item["finding_id"] for item in store.findings_for_pr(job["repository"], job["number"])
                            if item["status"] == "open"}
                value = finder_submission(payload["submission"], open_ids)
            else:
                value = voter_submission(payload["submission"], [item["candidateId"] for item in job["candidates"]])
            task = store.update_task(task_id, state="submitted", submission=value, digest=submitted,
                                     request_id=payload["requestId"], submitted_at=stamp(), expires_at=None)
            return self._receipt(advance(store, job_id, stamp()), task, now)

    @staticmethod
    def _receipt(job, task, now):
        return {"reviewJobId": job["job_id"], "taskId": task["task_id"], "role": task["role"], "state": task["state"],
                "phase": job["phase"], "serverNow": now}
