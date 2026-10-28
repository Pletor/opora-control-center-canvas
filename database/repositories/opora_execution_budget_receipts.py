"""Validate historical human-control receipts without exposing arbitrary stored JSON."""

from backend.canvas.opora_change_validation import identifier
from backend.canvas.opora_commit_validation import _author
from backend.canvas.opora_execution_budget_validation import execution_id, request_id
from backend.canvas.opora_review_policy_validation import timestamp


def policy_receipt(repo, result):
    if (
        set(result) != {"policyHead", "policy", "family"}
        or result["policyHead"] != result["policy"]["id"]
    ):
        raise ValueError("Invalid budget policy receipt shape.")
    family = result["family"]
    if not isinstance(family, dict) or set(family) != {
        "id",
        "acceptedRevision",
        "attempts",
        "repairRounds",
        "lastExecutionId",
        "hasReported",
    }:
        raise ValueError("Invalid stored family snapshot.")
    if (
        family["id"] != repo.family_id(result["policy"]["acceptedRevision"])
        or family["acceptedRevision"] != result["policy"]["acceptedRevision"]
        or type(family["attempts"]) is not int
        or family["attempts"] < 0
        or type(family["repairRounds"]) is not int
        or family["repairRounds"] < 0
        or type(family["hasReported"]) is not bool
    ):
        raise ValueError("Invalid stored family snapshot identity.")
    repo.family(family["acceptedRevision"])
    prefix = repo.events(family["acceptedRevision"])[: family["attempts"]]
    if (
        len(prefix) != family["attempts"]
        or family["repairRounds"] != sum(event["runKind"] == "repair" for event in prefix)
        or family["lastExecutionId"] != (prefix[-1]["executionId"] if prefix else None)
    ):
        raise ValueError("Stored family snapshot disagrees with consumption history.")


def cancellation(repo, event):
    keys = {
        "schemaVersion",
        "project",
        "workspace",
        "nodeId",
        "executionId",
        "epoch",
        "previousState",
        "state",
        "by",
        "createdAt",
        "requestId",
        "requestDigest",
        "id",
    }
    if (
        not isinstance(event, dict)
        or set(event) != keys
        or type(event["schemaVersion"]) is not int
        or event["schemaVersion"] != 1
    ):
        raise ValueError("Invalid budget cancellation shape.")
    repo.integrity(event, event["id"])
    execution_id(event["executionId"])
    identifier(event["requestDigest"])
    request_id(event["requestId"])
    timestamp(event["createdAt"])
    if (
        type(event["epoch"]) is not int
        or event["epoch"] < 1
        or event["previousState"] not in ("running", "released", "reported", "cancelled")
        or event["state"]
        != ("cancelled" if event["previousState"] == "running" else event["previousState"])
        or not isinstance(event["by"], dict)
        or set(event["by"]) != {"kind", "name"}
        or _author(event["by"], allow_agent=True)["kind"] not in ("human", "agent")  # agent = plná autonomie; kdo smí zapsat, hlídá brána zápisu (docs/plna-autonomie-agenta.md)
    ):
        raise ValueError("Invalid budget cancellation authority.")
    return event
