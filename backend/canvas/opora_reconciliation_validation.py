"""Strict immutable authority shapes for durable GitHub subscriptions."""
import re

from backend.canvas.opora_change_validation import identifier, scope
from backend.canvas.opora_commit_validation import _author
from backend.canvas.opora_reconciliation_observation import observation, semantic
from backend.canvas.opora_review_policy_validation import configuration, github_id, timestamp

# Deterministic server enrollment for a PR linked to an accepted execution (oporahub-executions.md).
AUTO_ENROLL_AUTHOR = {"kind": "system", "name": "Execution PR link"}


def validate(kind, record):
    fields = {"schemaVersion", "project", "workspace", "createdAt"}
    extra = {
        "binding": {"acceptedRevision", "identityEvidenceId", "repository", "pr", "enrolledHeadSha",
                    "configuration", "intervalSeconds", "by"},
        "control": {"bindingId", "parentControlId", "generation", "action", "enabled", "requestId", "requestDigest", "by"},
        "observation": {"bindingId", "data"},
        "event": {"bindingId", "eventKey", "observationId", "fromState", "toState"},
    }
    if not isinstance(record, dict) or kind not in extra or set(record) - {"id"} != fields | extra[kind]:
        raise ValueError("Invalid reconciliation record shape.")
    scope(record)
    if record.get("schemaVersion") != 1 or type(record.get("schemaVersion")) is not int:
        raise ValueError("Invalid reconciliation schema.")
    timestamp(record["createdAt"])
    if kind == "binding":
        identifier(record["acceptedRevision"])
        identifier(record["identityEvidenceId"])
        identifier(record["enrolledHeadSha"])
        repo, pr = record["repository"], record["pr"]
        if (not isinstance(repo, dict) or set(repo) != {"id", "fullName", "baseBranch"}
                or not isinstance(pr, dict) or set(pr) != {"id", "number", "headRepoId"}):
            raise ValueError("Invalid bound repository/PR shape.")
        github_id(repo["id"])
        configuration({"repository": repo["fullName"], "branch": repo["baseBranch"]})
        for key in ("id", "number", "headRepoId"):
            github_id(pr[key])
        if (record["intervalSeconds"] != 300 or set(record["configuration"]) != {"repository", "branch", "repoPath", "sourcePath"}
                or record["configuration"]["repository"] != repo["fullName"] or record["configuration"]["branch"] != repo["baseBranch"]):
            raise ValueError("Invalid bound configuration.")
        if record["by"] != AUTO_ENROLL_AUTHOR and (
                not isinstance(record["by"], dict) or set(record["by"]) != {"kind", "name"}
                or _author(record["by"])["kind"] != "human"):
            raise ValueError("Human subscription authority required.")
    elif kind == "control":
        if not isinstance(record["by"], dict) or set(record["by"]) != {"kind", "name"}:
            raise ValueError("Invalid control author shape.")
        identifier(record["bindingId"])
        identifier(record["parentControlId"], nullable=True)
        if (type(record["generation"]) is not int or record["generation"] < 1 or type(record["enabled"]) is not bool
                or record["action"] not in {"enroll", "pause", "resume", "retry", "system-pause", "auto-enroll"}):
            raise ValueError("Invalid reconciliation control.")
        system = {"system-pause": {"kind": "system", "name": "Reconciliation"}, "auto-enroll": AUTO_ENROLL_AUTHOR}
        if record["action"] not in system and _author(record["by"])["kind"] != "human":
            raise ValueError("Human subscription authority required.")
        if record["action"] in system:
            if (record["requestId"] is not None or record["requestDigest"] is not None
                    or record["by"] != system[record["action"]]):
                raise ValueError("Invalid automatic subscription authority.")
        else:
            if not isinstance(record["requestId"], str) or re.fullmatch(r"[A-Za-z0-9_-]{1,80}", record["requestId"]) is None:
                raise ValueError("Invalid control request identity.")
            identifier(record["requestDigest"])
        if record["enabled"] != (record["action"] in {"enroll", "resume", "retry", "auto-enroll"}):
            raise ValueError("Control action disagrees with enabled state.")
    elif kind in {"observation", "event"}:
        identifier(record["bindingId"])
        if kind == "observation":
            observation(record["data"])
        if kind == "event":
            identifier(record["observationId"])
            if not isinstance(record.get("eventKey"), str) or not 1 <= len(record["eventKey"]) <= 200:
                raise ValueError("Invalid transition key.")
            semantic(record["toState"])
            if record["fromState"] is not None:
                semantic(record["fromState"])
    else:
        raise ValueError("Unknown reconciliation record kind.")
    return record
