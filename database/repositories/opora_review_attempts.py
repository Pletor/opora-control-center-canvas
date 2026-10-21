"""Durable scoped observation ordering; newest pending and failed attempts remain authoritative."""
import re

from backend.canvas.opora_change_validation import identifier, scope
from backend.canvas.opora_review_policy_validation import configuration, timestamp

FIELDS = ("project", "workspace", "sequence", "prNumber", "configuredRepository", "configuredBranch", "acceptedRevision",
          "policyRevision", "startedAt", "finishedAt", "state", "evidenceId", "errorCode")
TERMINAL = {"complete", "failed", "context_changed"}


def number(value):
    if type(value) is not int or not 1 <= value <= 2147483647:
        raise ValueError("Invalid pull request number.")
    return value


def validate(record):
    scope(record)
    if type(record["sequence"]) is not int or not 1 <= record["sequence"] <= 9007199254740991:
        raise ValueError("Invalid observation attempt sequence.")
    number(record["prNumber"])
    configuration({"repository": record["configuredRepository"], "branch": record["configuredBranch"]})
    identifier(record["acceptedRevision"])
    identifier(record["policyRevision"], nullable=True)
    identifier(record["evidenceId"], nullable=True)
    started = timestamp(record["startedAt"])
    if record["state"] not in TERMINAL | {"pending"}:
        raise ValueError("Invalid observation attempt state.")
    if record["state"] == "pending":
        if any(record[key] is not None for key in ("finishedAt", "evidenceId", "errorCode")):
            raise ValueError("Pending attempt contains terminal evidence.")
    else:
        if timestamp(record["finishedAt"]) < started:
            raise ValueError("Attempt finished before it started.")
        if record["state"] == "complete" and (record["evidenceId"] is None or record["errorCode"] is not None):
            raise ValueError("Complete attempt requires evidence and no failure code.")
    error = record["errorCode"]
    if error is not None and (not isinstance(error, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,79}", error)):
        raise ValueError("Only bounded sanitized attempt error codes may be stored.")
    return record


class Attempts:
    def __init__(self, db, project, workspace):
        scope({"project": project, "workspace": workspace})
        self.db, self.scope = db, (project, workspace)

    def read(self, sequence):
        if type(sequence) is not int or sequence < 1:
            raise ValueError("Invalid observation attempt sequence.")
        row = self.db.execute("SELECT * FROM opora_review_attempts WHERE project_id=? AND workspace_id=? AND sequence=?",
                              (*self.scope, sequence)).fetchone()
        if row is None:
            raise ValueError("Observation attempt does not exist in this scope.")
        try:
            record = validate(dict(zip(FIELDS, row, strict=True)))
            if (record["project"], record["workspace"]) != self.scope or record["sequence"] != sequence:
                raise ValueError("Observation attempt scope mismatch.")
            return record
        except (KeyError, TypeError, AttributeError) as error:
            raise ValueError("Malformed stored observation attempt.") from error

    def begin(self, pr, config, accepted, policy, started):
        if not self.db.in_transaction:
            raise RuntimeError("Observation attempts require an explicit transaction.")
        repository, branch = configuration(config)
        previous = self.db.execute("SELECT MAX(sequence) FROM opora_review_attempts WHERE project_id=? AND workspace_id=?", self.scope).fetchone()[0]
        sequence = 1 if previous is None else previous + 1
        record = validate(dict(zip(FIELDS, (*self.scope, sequence, pr, repository, branch, accepted, policy,
                                           started, None, "pending", None, None), strict=True)))
        self.db.execute("INSERT INTO opora_review_attempts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", tuple(record[key] for key in FIELDS))
        return self.read(sequence)

    def finish(self, sequence, state, evidence_id, finished, error=None):
        if not self.db.in_transaction:
            raise RuntimeError("Finishing an attempt requires an explicit transaction.")
        if state not in TERMINAL:
            raise ValueError("Attempt completion requires a terminal state.")
        previous = self.read(sequence)
        proposed = validate({**previous, "state": state, "evidenceId": evidence_id, "finishedAt": finished, "errorCode": error})
        if previous["state"] != "pending":
            if previous == proposed:
                return previous
            raise ValueError("A terminal observation attempt cannot be rewritten.")
        changed = self.db.execute("UPDATE opora_review_attempts SET state=?,evidence_id=?,finished_at=?,error_code=? "
                                  "WHERE project_id=? AND workspace_id=? AND sequence=? AND state='pending'",
                                  (state, evidence_id, finished, error, *self.scope, sequence))
        if changed.rowcount != 1:
            raise ValueError("Observation attempt completion raced another writer.")
        return self.read(sequence)

    def latest(self, pr, config):
        number(pr)
        repository, branch = configuration(config)
        row = self.db.execute("SELECT sequence FROM opora_review_attempts WHERE project_id=? AND workspace_id=? "
                              "AND pr_number=? AND configured_repository=? AND configured_branch=? ORDER BY sequence DESC LIMIT 1",
                              (*self.scope, pr, repository, branch)).fetchone()
        return self.read(row[0]) if row else None
