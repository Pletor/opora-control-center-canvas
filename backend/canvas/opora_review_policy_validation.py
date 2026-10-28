"""Strict local review policy values; exact check identities and bounded account IDs."""
import re
from datetime import datetime, timedelta

from backend.canvas.opora_change_validation import identifier, scope
from backend.canvas.opora_commit_validation import _author

RULE_KEYS = {"requiredChecks", "reviewerIds", "minimumCodeApprovals", "minimumPlanApprovals", "maxObservationAgeSeconds"}
POLICY_KEYS = {"schemaVersion", "project", "workspace", "kind", "parentPolicyRevision", "enabled", "repository",
               "identityEvidenceId", "rules", "by", "createdAt"}


def github_id(value):
    if type(value) is not int or not 1 <= value <= 9007199254740991:
        raise ValueError("GitHub identity must be a positive safe integer.")
    return value


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
            raise ValueError("UTC timestamp required.")
        return parsed
    except (TypeError, AttributeError, OverflowError) as error:
        raise ValueError("Invalid UTC timestamp.") from error


def text(value, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or any(ord(char) < 32 for char in value):
        raise ValueError("Invalid bounded policy text.")
    return value


def configuration(config):
    if not isinstance(config, dict):
        raise ValueError("Invalid repository configuration.")  # noqa: TRY004 -- domain error maps to HTTP 409.
    repository, branch = config.get("repository"), config.get("branch")
    if not isinstance(repository, str) or not re.fullmatch(r"[a-z0-9-]+/[a-z0-9_-][a-z0-9._-]*", repository) or ".." in repository:
        raise ValueError("Invalid canonical GitHub repository.")
    text(repository, 255)
    text(branch, 255)
    return repository, branch


def rules(value):
    if not isinstance(value, dict) or set(value) != RULE_KEYS:
        raise ValueError("Invalid review policy rule fields.")
    checks, reviewers = value["requiredChecks"], value["reviewerIds"]
    if not isinstance(checks, list) or not 1 <= len(checks) <= 32:
        raise ValueError("Policy requires between 1 and 32 exact check pairs.")
    pairs = []
    for check in checks:
        if not isinstance(check, dict) or set(check) != {"appId", "name"}:
            raise ValueError("Each required check needs only appId and name.")
        pairs.append((github_id(check["appId"]), text(check["name"], 255)))
    if len(set(pairs)) != len(pairs):
        raise ValueError("Required check pairs must be distinct.")
    if not isinstance(reviewers, list) or not 1 <= len(reviewers) <= 100:
        raise ValueError("Policy requires between 1 and 100 reviewer account IDs.")
    reviewers = [github_id(item) for item in reviewers]
    if len(set(reviewers)) != len(reviewers):
        raise ValueError("Reviewer account IDs must be unique.")
    for key in ("minimumCodeApprovals", "minimumPlanApprovals"):
        if type(value[key]) is not int or not 1 <= value[key] <= len(reviewers):
            raise ValueError("Approval minimum must fit the reviewer allowlist.")
    age = value["maxObservationAgeSeconds"]
    if type(age) is not int or not 30 <= age <= 3600:
        raise ValueError("Observation age must be between 30 and 3600 seconds.")
    return {**value, "requiredChecks": [{"appId": app, "name": name} for app, name in sorted(pairs)], "reviewerIds": sorted(reviewers)}


def validate_policy(record):
    if not isinstance(record, dict) or set(record) - {"id"} != POLICY_KEYS:
        raise ValueError("Invalid immutable review policy fields.")
    scope(record)
    if "id" in record:
        identifier(record["id"])
    if type(record["schemaVersion"]) is not int or record["schemaVersion"] != 1 or record["kind"] != "review-policy":
        raise ValueError("Invalid review policy kind/version.")
    identifier(record["parentPolicyRevision"], nullable=True)
    identifier(record["identityEvidenceId"])
    if type(record["enabled"]) is not bool:
        raise ValueError("Policy enabled must be a boolean.")
    repository = record["repository"]
    if not isinstance(repository, dict) or set(repository) != {"id", "fullName", "baseBranch"}:
        raise ValueError("Invalid pinned repository identity.")
    github_id(repository["id"])
    configuration({"repository": repository["fullName"], "branch": repository["baseBranch"]})
    if rules(record["rules"]) != record["rules"]:
        raise ValueError("Stored policy rules are not canonical.")
    if not isinstance(record["by"], dict) or set(record["by"]) != {"kind", "name"} or _author(record["by"], allow_agent=True)["kind"] not in ("human", "agent"):
        raise ValueError("Policy revisions require a human author.")
    timestamp(record["createdAt"])
    return record
