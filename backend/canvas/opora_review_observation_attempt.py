"""Short transactions bracket network collection; latest-started attempt wins."""
from datetime import UTC, datetime

from backend.canvas.opora_commit_validation import _author
from backend.canvas.opora_formal_checks import ingest_snapshot
from backend.canvas.opora_review_scope import context, validate_request
from backend.integrations.github_review_transport import GitHubReadError
from database.repositories.opora_review_attempts import Attempts
from database.repositories.opora_review_policy import Policies


def stamp():
    return datetime.now(UTC).isoformat()


class PolicyObservation:
    def __init__(self, evidence):
        self.evidence, self.service = evidence, evidence.service

    def begin(self, payload):
        pid, wid = payload["project"], payload["workspace"]
        with self.service.graph_lock_for(pid), self.service.lock_for(pid):
            db = self.service.db_for(pid)
            with db:
                db.execute("BEGIN IMMEDIATE")
                before = context(self.service, pid, wid)
                self.evidence._check(before, payload)
                policy = Policies(db, pid, wid).head()
                if policy:
                    Policies(db, pid, wid).read(policy)
                attempt = Attempts(db, pid, wid).begin(payload["prNumber"], before["config"],
                                                       before["acceptedHead"], policy, stamp())
            return before, attempt

    def observe(self, payload, by):
        validate_request(payload)
        by = _author(by, allow_agent=True)
        before, attempt = self.begin(payload)
        mismatch = False
        try:
            data = self.evidence.reader.read(before["repository"], payload["prNumber"])
        except GitHubReadError:
            data = {"complete": False, "errorCode": "github-observation-unavailable"}
        if data.get("complete") is True:
            mismatch = (data["repository"]["fullName"].casefold() != before["repository"]
                        or data["pr"]["number"] != payload["prNumber"]
                        or data["pr"]["baseRef"] != before["config"]["branch"]
                        or ("expectedHeadSha" in payload and data["pr"]["headSha"] != payload["expectedHeadSha"]))
        return self.finish(payload, by, before, attempt, data, mismatch)

    def finish(self, payload, by, before, attempt, data, mismatch):
        pid, wid = payload["project"], payload["workspace"]
        conflict, record, current = None, None, None
        with self.service.graph_lock_for(pid), self.service.lock_for(pid):
            repo = self.evidence.repository(pid, wid)
            attempts = Attempts(repo.db, pid, wid)
            with repo.db:
                repo.db.execute("BEGIN IMMEDIATE")
                try:
                    current = context(self.service, pid, wid)
                    self.evidence._check(current, payload)
                    if current["config"] != before["config"]:
                        raise ValueError("Repository configuration changed during observation.")
                    if Policies(repo.db, pid, wid).head() != attempt["policyRevision"]:
                        raise ValueError("Review policy changed during observation; refresh evidence.")
                except ValueError as error:
                    conflict = error
                finished = stamp()
                if conflict is not None or mismatch:
                    code = "observation-context-changed" if conflict else "github-identity-mismatch"
                    attempts.finish(attempt["sequence"], "context_changed", None, finished, code)
                    conflict = conflict or ValueError("PR, target branch or SHA does not match this project.")
                else:
                    content = {**data, "schemaVersion": 2, "project": pid, "workspace": wid,
                               "acceptedRevision": before["acceptedHead"], "initiatedBy": by,
                               "configuredRepository": before["repository"],
                               "configuredBaseBranch": before["config"]["branch"], "prNumber": payload["prNumber"],
                               "observedAt": finished, "observedFrom": attempt["startedAt"], "observedUntil": finished,
                               "attemptSequence": attempt["sequence"]}
                    record = repo.insert(content)
                    ingest_snapshot(repo.db, pid, wid, content)
                    state = "complete" if data.get("complete") is True else "failed"
                    attempts.finish(attempt["sequence"], state, record["id"], finished,
                                    None if state == "complete" else "github-observation-unavailable")
            if conflict is not None:
                raise conflict
            return self.evidence._item(record, current, repo)
