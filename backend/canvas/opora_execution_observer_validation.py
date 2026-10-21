"""Bounded public broker attestations; no provider payload or worker capability."""
import math
import re
import time

from backend.canvas.graph import valid_id
from backend.canvas.opora_change_validation import identifier, scope
from backend.canvas.opora_execution_budget_validation import budget, execution_id, request_id
from backend.canvas.opora_execution_observer_auth import PROVIDER, money
from backend.canvas.opora_review_policy_validation import timestamp
from backend.editor.node.drawings import _json_safe

INTENT_KEYS = {"project", "workspace", "requestId", "executionId", "nodeId", "epoch",
               "acceptedRevision", "assignmentDigest", "contextProtocolVersion", "contextVersion",
               "executionProtocolVersion", "budget", "authorityDeadlineAt", "provider", "repository",
               "agentId", "agentVersion", "environmentId", "environmentDigest", "configurationDigest",
               "maxListCostCents"}
OBSERVATION_KEYS = {"project", "workspace", "intentId", "requestId", "expectedObservationHead",
                    "sequence", "sessionId", "observedAt", "source", "status", "providerStatus", "cumulative"}
COUNTERS = {"inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreation5mTokens", "cacheCreation1hTokens"}
STATUSES = {"creating", "creation_unknown", "running", "idle", "termination_pending", "terminated", "failed", "unknown"}


def exact(value, keys):
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("Invalid observer record fields.")
    _json_safe(value)
    scope(value)
    request_id(value["requestId"])


def hex64(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ValueError("Invalid public configuration digest.")


def positive(value):
    if type(value) is not int or not 1 <= value <= 9007199254740991:
        raise ValueError("A positive safe integer is required.")


def resource_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", value):
        raise ValueError("Invalid provider resource identifier.")


def intent(value):
    exact(value, INTENT_KEYS)
    execution_id(value["executionId"])
    if not valid_id(value["nodeId"]):
        raise ValueError("Invalid bound node.")
    for key in ("epoch", "agentVersion"):
        positive(value[key])
    identifier(value["acceptedRevision"])
    for key in ("assignmentDigest", "contextVersion", "environmentDigest", "configurationDigest"):
        hex64(value[key])
    if type(value["contextProtocolVersion"]) is not int or value["contextProtocolVersion"] not in (1, 2):
        raise ValueError("Unsupported bound context protocol.")
    if type(value["executionProtocolVersion"]) is not int or value["executionProtocolVersion"] != 2:
        raise ValueError("Isolated execution requires budget protocol two.")
    allocation = budget(value["budget"])
    if type(value["authorityDeadlineAt"]) not in (int, float) or value["authorityDeadlineAt"] != allocation["runDeadlineAt"]:
        raise ValueError("Intent authority deadline differs from its immutable allocation.")
    if value["provider"] != PROVIDER:
        raise ValueError("Unsupported isolated provider.")
    repo = value["repository"]
    if not isinstance(repo, dict) or set(repo) != {"url", "commitSha"}:
        raise ValueError("A pinned repository is required.")
    if not isinstance(repo["url"], str) or not re.fullmatch(r"https://github\.com/[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+", repo["url"]) or ".." in repo["url"]:
        raise ValueError("A canonical HTTPS GitHub repository is required.")
    identifier(repo["commitSha"])
    for key in ("agentId", "environmentId"):
        resource_id(value[key])
    money(value["maxListCostCents"], positive=True)
    return value


def observation(value, *, check_future=True):
    exact(value, OBSERVATION_KEYS)
    identifier(value["intentId"])
    identifier(value["expectedObservationHead"], nullable=True)
    positive(value["sequence"])
    if value["sessionId"] is not None:
        resource_id(value["sessionId"])
    stamp = timestamp(value["observedAt"]).timestamp()
    if stamp < 0 or (check_future and stamp > time.time() + 300):
        raise ValueError("Observation timestamp is outside its allowed range.")
    if value["source"] != "provider-api" or value["status"] not in STATUSES:
        raise ValueError("Invalid provider observation status or source.")
    if value["providerStatus"] not in (None, "idle", "running", "rescheduling", "terminated"):
        raise ValueError("Invalid provider readback status.")
    if (value["status"] == "terminated") != (value["providerStatus"] == "terminated"):
        raise ValueError("Termination requires matching provider readback.")
    cumulative = value["cumulative"]
    if not isinstance(cumulative, dict) or set(cumulative) != COUNTERS | {"listCostCents", "currency", "activeSeconds"}:
        raise ValueError("Invalid cumulative usage fields.")
    for key in COUNTERS:
        if type(cumulative[key]) is not int or not 0 <= cumulative[key] <= 9007199254740991:
            raise ValueError("Invalid cumulative token counter.")
    seconds = cumulative["activeSeconds"]
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 <= seconds <= 9007199254740991:
        raise ValueError("Invalid cumulative active seconds.")
    money(cumulative["listCostCents"])
    if cumulative["currency"] != "USD":
        raise ValueError("Provider list cost must use USD.")
    if value["sessionId"] is None and (value["status"] not in {"creating", "creation_unknown", "unknown"}
                                     or any(cumulative[key] for key in COUNTERS | {"activeSeconds"})
                                     or cumulative["listCostCents"] != "0" or value["providerStatus"] is not None):
        raise ValueError("Usage or provider state requires a bound session.")
    return value


def advance(previous, value):
    if value["sequence"] != (previous["sequence"] + 1 if previous else 1):
        raise ValueError("Observation sequence must advance exactly once.")
    if not previous:
        return
    if timestamp(value["observedAt"]) < timestamp(previous["observedAt"]):
        raise ValueError("Observation time cannot rewind.")
    if previous["sessionId"] is not None and value["sessionId"] != previous["sessionId"]:
        raise ValueError("A billing session cannot change.")
    if previous["status"] == "terminated" and value["status"] != "terminated":
        raise ValueError("Verified termination cannot be revoked by later usage.")
    for key in COUNTERS | {"activeSeconds", "listCostCents"}:
        before, after = previous["cumulative"][key], value["cumulative"][key]
        if (int(after) if key == "listCostCents" else after) < (int(before) if key == "listCostCents" else before):
            raise ValueError("Cumulative usage cannot decrease.")
