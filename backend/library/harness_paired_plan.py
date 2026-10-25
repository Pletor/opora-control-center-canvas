"""Read and validate a pinned paired-evaluation plan from one accepted execution."""
import hashlib
import json
import re

from backend.library.harness_adapter_kit import validate_adapter_kit

IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@/+-]{0,199}\Z")
PLAN_SCHEMA = "harness.paired-node/1"
MAX_PLAN_BYTES = 32 * 1024
MAX_SCRIPT_BYTES = 96 * 1024


def _fail():
    raise ValueError("Invalid accepted paired plan.")


def _id(value):
    return isinstance(value, str) and IDENTIFIER.fullmatch(value) is not None


def _text(value, limit):
    if not isinstance(value, str) or "\0" in value:
        return False
    try:
        return len(value.encode("utf-8", "strict")) <= limit
    except UnicodeError:
        return False


def _digest(content):
    return hashlib.sha256(content.encode("utf-8", "strict")).hexdigest()


def _exact(value, keys):
    return isinstance(value, dict) and set(value) == keys


def accepted_plan(record, reference):
    """Return detached plan/resource metadata after checking exact accepted v2 authority."""
    if (not isinstance(record, dict) or type(record.get("contextProtocolVersion")) is not int
            or record["contextProtocolVersion"] != 2 or not _id(record.get("nodeId"))
            or not _exact(reference, {"id", "digest"}) or not _id(reference.get("id"))
            or not isinstance(reference.get("digest"), str)
            or re.fullmatch(r"[a-f0-9]{64}", reference["digest"]) is None):
        _fail()
    assignment = record.get("assignment")
    documents = assignment.get("documents") if isinstance(assignment, dict) else None
    if not isinstance(documents, list):
        _fail()
    targets = [doc for doc in documents if isinstance(doc, dict) and doc.get("nodeId") == record["nodeId"]]
    if len(targets) != 1:
        _fail()
    fields = targets[0].get("fields")
    kit = fields.get("harness") if isinstance(fields, dict) else None
    if (not isinstance(kit, dict)
            or kit.get("problems") != ["evaluation:paired-node"]
            or not isinstance(kit.get("resources"), list) or len(kit["resources"]) > 24):
        _fail()
    validate_adapter_kit(kit)
    resources = kit["resources"]
    plans = [item for item in resources if isinstance(item, dict) and item.get("resource") == reference["id"]]
    if len(plans) != 1:
        _fail()
    plan_resource = plans[0]
    if (plan_resource.get("category") != "testing" or plan_resource.get("requires") != []
            or plan_resource.get("digest") != reference["digest"]
            or not _text(plan_resource.get("content"), MAX_PLAN_BYTES)
            or _digest(plan_resource["content"]) != reference["digest"]):
        _fail()
    try:
        plan = json.loads(plan_resource["content"])
    except (json.JSONDecodeError, UnicodeError):
        _fail()
    if (not _exact(plan, {"schema", "problem", "baseline", "candidate", "cases"})
            or plan["schema"] != PLAN_SCHEMA or not _id(plan["problem"])
            or not _id(plan["baseline"]) or not _id(plan["candidate"])
            or len({plan["baseline"], plan["candidate"], reference["id"]}) != 3
            or not isinstance(plan["cases"], list) or not 1 <= len(plan["cases"]) <= 8):
        _fail()
    seen = set()
    cases = []
    for case in plan["cases"]:
        if (not _exact(case, {"id", "args", "expectedStdout"}) or not _id(case["id"])
                or case["id"] in seen or not isinstance(case["args"], list) or len(case["args"]) > 32
                or any(not _text(arg, 16 * 1024) for arg in case["args"])
                or not _text(case["expectedStdout"], 8 * 1024)):
            _fail()
        try:
            encoded_args = json.dumps(case["args"], ensure_ascii=False, separators=(",", ":")).encode("utf-8", "strict")
        except (TypeError, UnicodeError):
            _fail()
        if len(encoded_args) > 16 * 1024:
            _fail()
        seen.add(case["id"])
        cases.append({"id": case["id"], "args": list(case["args"]), "expectedStdout": case["expectedStdout"]})

    def script(resource_id):
        matches = [item for item in resources if isinstance(item, dict) and item.get("resource") == resource_id]
        if len(matches) != 1:
            _fail()
        item = matches[0]
        content = item.get("content")
        if (item.get("category") != "scripts" or item.get("requires") != ["command:node"]
                or not _text(content, MAX_SCRIPT_BYTES) or _digest(content) != item.get("digest")):
            _fail()
        return {"id": resource_id, "digest": item["digest"]}

    return {"plan": {"schema": PLAN_SCHEMA, "problem": plan["problem"], "baseline": plan["baseline"],
                      "candidate": plan["candidate"], "cases": cases},
            "baseline": script(plan["baseline"]), "candidate": script(plan["candidate"]),
            "resource": {"id": reference["id"], "digest": reference["digest"]}}
