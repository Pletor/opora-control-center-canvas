"""Strict immutable policy, allocation and server-clock values."""

import math
import re

from backend.canvas.opora_change_validation import identifier, scope
from backend.canvas.opora_commit_validation import _author
from backend.canvas.opora_review_policy_validation import timestamp

BUDGET_KEYS = {
    "policyHead",
    "familyId",
    "allocationId",
    "attempt",
    "repairRound",
    "kind",
    "admittedAt",
    "runDeadlineAt",
    "maxRunSeconds",
}


def request_id(value):
    if not isinstance(value, str) or re.fullmatch("[A-Za-z0-9_-]{1,80}", value) is None:
        raise ValueError("Invalid budget request ID.")


def execution_id(value, nullable=False):
    if nullable and value is None:
        return
    if not isinstance(value, str) or re.fullmatch("[a-f0-9]{32}", value) is None:
        raise ValueError("Invalid predecessor execution ID.")


def limits(value):
    bounds = {"maxRunSeconds": (30, 86400), "maxAttempts": (1, 100), "maxRepairRounds": (0, 99)}
    if not isinstance(value, dict) or set(value) != set(bounds):
        raise ValueError("Budget requires exactly three limits.")
    if any(type(value[k]) is not int or not lo <= value[k] <= hi for k, (lo, hi) in bounds.items()):
        raise ValueError("Budget limits must be bounded integers.")
    if value["maxRepairRounds"] >= value["maxAttempts"]:
        raise ValueError("Repair rounds cannot exceed attempts minus one.")
    return value


def finite(value):
    if (
        type(value) not in (int, float)
        or not 0 <= value <= 253402300799
        or not math.isfinite(value)
    ):
        raise ValueError("Invalid server budget time.")
    return value


def policy(value):
    fields = {
        "schemaVersion",
        "project",
        "workspace",
        "nodeId",
        "acceptedRevision",
        "parentPolicyHead",
        "limits",
        "by",
        "createdAt",
        "requestId",
        "requestDigest",
    }
    if (
        not isinstance(value, dict)
        or set(value) - {"id"} != fields
        or type(value["schemaVersion"]) is not int
        or value["schemaVersion"] != 1
    ):
        raise ValueError("Invalid budget policy shape.")
    scope(value)
    if (
        not isinstance(value["nodeId"], str)
        or re.fullmatch("[A-Za-z0-9_-]{1,80}", value["nodeId"]) is None
    ):
        raise ValueError("Invalid budget target.")
    identifier(value["acceptedRevision"])
    identifier(value["parentPolicyHead"], nullable=True)
    limits(value["limits"])
    if (
        not isinstance(value["by"], dict)
        or set(value["by"]) != {"kind", "name"}
        or _author(value["by"])["kind"] != "human"
    ):
        raise ValueError("Budget policy requires a human author.")
    timestamp(value["createdAt"])
    request_id(value["requestId"])
    identifier(value["requestDigest"])
    return value


def budget(value):
    if not isinstance(value, dict) or set(value) != BUDGET_KEYS:
        raise ValueError("Invalid immutable execution budget.")
    for key in ("policyHead", "familyId", "allocationId"):
        identifier(value[key])
    if (
        type(value["attempt"]) is not int
        or not 1 <= value["attempt"] <= 9007199254740991
        or type(value["repairRound"]) is not int
        or not 0 <= value["repairRound"] < value["attempt"]
    ):
        raise ValueError("Invalid budget allocation counters.")
    if (
        value["kind"] not in ("initial", "retry", "repair")
        or type(value["maxRunSeconds"]) is not int
        or not 30 <= value["maxRunSeconds"] <= 86400
    ):
        raise ValueError("Invalid budget allocation kind or deadline.")
    if (
        value["kind"] == "initial"
        and (value["attempt"] != 1 or value["repairRound"] != 0)
        or value["kind"] == "retry"
        and (value["attempt"] <= 1 or value["repairRound"] != 0)
        or value["kind"] == "repair"
        and value["repairRound"] < 1
    ):
        raise ValueError("Budget kind disagrees with its ordinal.")
    if finite(value["runDeadlineAt"]) != finite(value["admittedAt"]) + value["maxRunSeconds"]:
        raise ValueError("Budget deadline differs from its admitted limit.")
    return value
