"""Validate bounded worker-observed Harness invocation metadata."""
import hashlib
import math
import re
import uuid

from backend.library.harness_adapter_kit import validate_adapter_kit

OBSERVATION_KEYS = {
    "schema", "invocationId", "execution", "resource", "adapter", "nodeVersion",
    "exitCode", "reason", "durationMs", "outputBytes", "outcome",
    "authorityCurrentAtCompletion", "cleanupComplete", "evidence",
    "independentlyVerified", "causalContribution", "promotionAllowed", "tokens", "cost",
}
EXECUTION_KEYS = {"executionId", "epoch", "project", "workspace", "nodeId", "acceptedRevision", "assignmentDigest"}
RESOURCE_KEYS = {"id", "digest"}
REASONS = {"completed", "nonzero-exit", "timeout", "output-limit", "execution-changed",
           "execution-unavailable", "spawn-failed"}
NODE_VERSION = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+\Z")


def _fail():
    raise ValueError("Invalid Harness invocation metadata.")


def validate_invocations(result, record):
    """Validate receipt metadata against the exact script pinned in an accepted v2 assignment."""
    if not isinstance(result, dict):
        _fail()
    if "harnessInvocations" not in result:
        return []
    items = result["harnessInvocations"]
    if not isinstance(items, list) or len(items) > 32:
        _fail()
    if not isinstance(record, dict) or type(record.get("contextProtocolVersion")) is not int or record["contextProtocolVersion"] != 2:
        _fail()
    assignment = record.get("assignment")
    if not isinstance(assignment, dict) or not isinstance(assignment.get("documents"), list):
        _fail()
    targets = [doc for doc in assignment["documents"] if isinstance(doc, dict) and doc.get("nodeId") == record.get("nodeId")]
    if len(targets) != 1:
        _fail()
    fields = targets[0].get("fields")
    kit = fields.get("harness") if isinstance(fields, dict) else None
    if not isinstance(kit, dict) or not isinstance(kit.get("resources"), list):
        _fail()
    validate_adapter_kit(kit)
    pinned = {}
    for resource in kit["resources"]:
        if isinstance(resource, dict) and resource.get("category") == "scripts":
            resource_id, content = resource.get("resource"), resource.get("content")
            if isinstance(resource_id, str) and isinstance(content, str):
                pinned.setdefault(resource_id, []).append(
                    (resource, hashlib.sha256(content.encode("utf-8", "strict")).hexdigest()))
    seen = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != OBSERVATION_KEYS:
            _fail()
        try:
            if str(uuid.UUID(item["invocationId"])) != item["invocationId"]:
                _fail()
        except (ValueError, TypeError, AttributeError):
            _fail()
        if item["invocationId"] in seen:
            _fail()
        seen.add(item["invocationId"])
        if item["schema"] != "harness.invocation-metadata/1":
            _fail()
        execution = item["execution"]
        if not isinstance(execution, dict) or set(execution) != EXECUTION_KEYS:
            _fail()
        for key in EXECUTION_KEYS - {"epoch"}:
            if execution[key] != record.get(key):
                _fail()
        if type(execution["epoch"]) is not int or execution["epoch"] != record.get("epoch"):
            _fail()
        resource = item["resource"]
        if not isinstance(resource, dict) or set(resource) != RESOURCE_KEYS:
            _fail()
        if not isinstance(resource["id"], str):
            _fail()
        matches = pinned.get(resource["id"], [])
        if (len(matches) != 1 or matches[0][0].get("digest") != resource["digest"]
                or matches[0][1] != resource["digest"]
                or matches[0][0].get("requires") != ["command:node"]):
            _fail()
        if (item["adapter"] != "node-readonly/1" or not isinstance(item["nodeVersion"], str)
                or len(item["nodeVersion"]) > 64 or not NODE_VERSION.fullmatch(item["nodeVersion"])):
            _fail()
        code = item["exitCode"]
        if code is not None and (type(code) is not int or not -(2 ** 31) <= code <= 2 ** 32 - 1):
            _fail()
        if not isinstance(item["reason"], str) or item["reason"] not in REASONS:
            _fail()
        duration = item["durationMs"]
        if (isinstance(duration, bool) or not isinstance(duration, (int, float))
                or not 0 <= duration <= 60000 or not math.isfinite(duration)):
            _fail()
        output = item["outputBytes"]
        if type(output) is not int or not 0 <= output <= 1024 ** 3:
            _fail()
        for key in ("authorityCurrentAtCompletion", "cleanupComplete"):
            if type(item[key]) is not bool:
                _fail()
        if (item["evidence"] != "worker-observed" or item["independentlyVerified"] is not False
                or item["causalContribution"] is not False or item["promotionAllowed"] is not False
                or item["tokens"] is not None or item["cost"] is not None):
            _fail()
        expected = (item["reason"] == "completed" and code == 0
                    and item["authorityCurrentAtCompletion"] and item["cleanupComplete"])
        if item["outcome"] != ("pass" if expected else "fail"):
            _fail()
    return items
