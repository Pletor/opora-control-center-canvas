"""Stored ledger validation; malformed counters cannot grant additional authority."""

from backend.canvas.opora_change_validation import identifier
from backend.canvas.opora_execution_budget_validation import budget, execution_id, policy
from backend.canvas.opora_review_policy_validation import timestamp


def ledger(value, previous):
    common = {
        "id",
        "schemaVersion",
        "project",
        "workspace",
        "nodeId",
        "acceptedRevision",
        "familyId",
        "sequence",
        "parentId",
        "kind",
        "executionId",
        "runKind",
        "createdAt",
    }
    allocation = {
        "attempt",
        "repairRound",
        "previousExecutionId",
        "policyHead",
        "policySnapshot",
        "admittedAt",
        "runDeadlineAt",
        "maxRunSeconds",
    }
    legacy = {"legacyReported", "legacyRecordDigest"}
    if not isinstance(value, dict) or value.get("kind") not in ("allocation", "legacy-import"):
        raise ValueError("Invalid budget ledger record kind.")
    if set(value) != common | (allocation if value["kind"] == "allocation" else legacy):
        raise ValueError("Invalid budget ledger shape.")
    if (
        type(value["schemaVersion"]) is not int
        or value["schemaVersion"] != 1
        or type(value["sequence"]) is not int
        or value["sequence"] != len(previous) + 1
    ):
        raise ValueError("Invalid budget ledger sequence.")
    execution_id(value["executionId"])
    for key in ("acceptedRevision", "familyId", "id"):
        identifier(value[key])
    identifier(value["parentId"], nullable=True)
    timestamp(value["createdAt"])
    if value["runKind"] not in ("initial", "retry", "repair") or (value["sequence"] == 1) != (
        value["runKind"] == "initial"
    ):
        raise ValueError("Invalid budget run classification.")
    if value["kind"] == "legacy-import":
        if type(value["legacyReported"]) is not bool:
            raise ValueError("Invalid imported result marker.")
        identifier(value["legacyRecordDigest"])
    else:
        policy(value["policySnapshot"])
        if (
            value["policyHead"] != value["policySnapshot"]["id"]
            or value["policySnapshot"]["acceptedRevision"] != value["acceptedRevision"]
            or value["attempt"] != value["sequence"]
            or value["previousExecutionId"] != (previous[-1]["executionId"] if previous else None)
            or value["repairRound"]
            != sum(item["runKind"] == "repair" for item in previous)
            + (value["runKind"] == "repair")
        ):
            raise ValueError("Invalid budget allocation provenance or ordinal.")
        budget(
            {
                "policyHead": value["policyHead"],
                "familyId": value["familyId"],
                "allocationId": value["id"],
                "attempt": value["attempt"],
                "repairRound": value["repairRound"],
                "kind": value["runKind"],
                "admittedAt": value["admittedAt"],
                "runDeadlineAt": value["runDeadlineAt"],
                "maxRunSeconds": value["maxRunSeconds"],
            }
        )
    return value
