"""Validate reported documentation reads, never task-success or independent evidence."""
import hashlib
import json
import math
import re
import uuid
from datetime import datetime

from backend.library.harness_adapter_kit import validate_adapter_kit

EXECUTION = {"executionId", "epoch", "project", "workspace", "nodeId", "acceptedRevision", "assignmentDigest"}
KEYS = {"schema", "readId", "execution", "resource", "adapter", "library", "documentDigest", "fetchedAt",
        "durationMs", "outputBytes", "evidence", "independentlyVerified", "causalContribution", "promotionAllowed"}


def invalid():
    raise ValueError("Invalid Harness documentation observation.")


def validate_documentation(result, record):
    if not isinstance(result, dict):
        invalid()
    if "harnessDocumentation" not in result:
        return []
    items = result["harnessDocumentation"]
    if not isinstance(items, list) or len(items) > 32:
        invalid()
    if not isinstance(record, dict) or type(record.get("contextProtocolVersion")) is not int or record["contextProtocolVersion"] != 2:
        invalid()
    assignment = record.get("assignment", {})
    docs = assignment.get("documents") if isinstance(assignment, dict) else None
    if not isinstance(docs, list):
        invalid()
    targets = [d for d in docs if isinstance(d, dict) and d.get("nodeId") == record.get("nodeId")]
    if len(targets) != 1 or not isinstance(targets[0].get("fields"), dict):
        invalid()
    kit = targets[0]["fields"].get("harness")
    validate_adapter_kit(kit)
    if not isinstance(kit.get("resources"), list):
        invalid()
    seen = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != KEYS:
            invalid()
        try:
            if str(uuid.UUID(item["readId"])) != item["readId"] or item["readId"] in seen:
                invalid()
        except (ValueError, TypeError, AttributeError):
            invalid()
        seen.add(item["readId"])
        execution = item["execution"]
        if (not isinstance(execution, dict) or set(execution) != EXECUTION
                or any(execution[k] != record.get(k) for k in EXECUTION)
                or type(execution["epoch"]) is not int):
            invalid()
        resource = item["resource"]
        if not isinstance(resource, dict) or set(resource) != {"id", "digest"}:
            invalid()
        matches = [r for r in kit["resources"] if isinstance(r, dict) and r.get("resource") == resource["id"]]
        if len(matches) != 1:
            invalid()
        pinned = matches[0]
        content = pinned.get("content")
        if (pinned.get("category") != "mcp" or pinned.get("requires") != ["mcp:context7"]
                or not isinstance(content, str) or len(content) > 98304):
            invalid()
        try:
            digest = hashlib.sha256(content.encode("utf-8", "strict")).hexdigest()
            config = json.loads(content)
        except (ValueError, UnicodeError):
            invalid()
        if (digest != resource["digest"] or digest != pinned.get("digest") or not isinstance(config, dict)
                or set(config) != {"schema", "library"} or config["schema"] != "harness.context7/1"
                or not isinstance(config["library"], str) or len(config["library"]) > 200
                or not re.fullmatch(r"/[A-Za-z0-9_.@+-]+/[A-Za-z0-9_./@+-]+", config["library"])
                or item["library"] != config["library"]):
            invalid()
        if (item["schema"] != "harness.documentation-observation/1"
                or item["adapter"] != "context7-documentation/1" or item["evidence"] != "worker-reported"
                or any(item[k] is not False for k in ("independentlyVerified", "causalContribution", "promotionAllowed"))
                or not isinstance(item["documentDigest"], str) or not re.fullmatch(r"[a-f0-9]{64}", item["documentDigest"])):
            invalid()
        duration = item["durationMs"]
        if (isinstance(duration, bool) or not isinstance(duration, (int, float))
                or not 0 <= duration <= 60000 or not math.isfinite(duration)
                or type(item["outputBytes"]) is not int or not 1 <= item["outputBytes"] <= 65536):
            invalid()
        try:
            stamp = item["fetchedAt"]
            if not isinstance(stamp, str) or len(stamp) > 40 or not stamp.endswith("Z"):
                invalid()
            datetime.fromisoformat(stamp)
        except ValueError:
            invalid()
    return items
