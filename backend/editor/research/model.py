"""Strict research graph payload validation; limits reject rather than truncate."""
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.graph import valid_id

KINDS = {"question", "finding", "visual", "option", "decision"}
RELATIONS = {"supports", "contradicts", "elaborates", "option_for", "supersedes", "resolves", "continues_to"}
VERIFICATION = {"unverified", "verified", "observed", "false", "unreachable", "inference", "conflict"}
REFS = {"nodeIds", "questionIds", "ticketIds", "sessionIds", "fragmentIds", "attachmentIds"}
CARD = {"kind", "title", "summary", "topicPath", "content", "status", "verification", "sources", "refs"}
EDGE = {"fromId", "toId", "relation", "reason", "resolved", "missing", "evidenceIds"}


def fail(message, status=422, code="research_invalid"):
    raise GateError(status, code, message, "Read /api/research and retry with current revisions.")


def text(value, field, limit=10000, empty=True):
    if not isinstance(value, str) or len(value) > limit or "\0" in value or (not empty and not value.strip()):
        fail(f"{field}: expected {'nonempty ' if not empty else ''}text up to {limit} characters.")
    return value


def identifier(value):
    if not isinstance(value, str) or not valid_id(value):
        fail("Invalid identifier.")
    return value


def strings(value, field, limit=1000, ids=False):
    if not isinstance(value, list) or len(value) > limit:
        fail(f"{field}: expected array of at most {limit} strings.")
    for item in value:
        identifier(item) if ids else text(item, field, 1000, False)
    if len(set(value)) != len(value):
        fail(f"{field}: duplicate values.")


def shape(value, required, optional=frozenset()):
    if not isinstance(value, dict) or required - value.keys() or value.keys() - required - optional:
        fail("Expected fields: " + ", ".join(sorted(required)))


def card(value):
    shape(value, CARD)
    text(value["kind"], "kind", 30)
    text(value["status"], "status", 30)
    if value["kind"] not in KINDS or value["status"] not in ("open", "resolved"):
        fail("Invalid card kind or status.")
    text(value["title"], "title", 500, False)
    text(value["summary"], "summary", 4000, False)
    text(value["content"], "content", 2_000_000)
    strings(value["topicPath"], "topicPath", 50)
    if not value["topicPath"]:
        fail("topicPath must identify the problem.")
    verification = value["verification"]
    shape(verification, {"status", "method", "at"})
    text(verification["status"], "verification.status", 30)
    if verification["status"] not in VERIFICATION:
        fail("Invalid verification status.")
    text(verification["method"], "verification.method", 4000)
    text(verification["at"], "verification.at", 100)
    if verification["status"] in ("verified", "observed") and (not verification["method"].strip() or not verification["at"].strip()):
        fail("Verified or observed findings require verification method and time.")
    sources = value["sources"]
    if not isinstance(sources, list) or len(sources) > 1000:
        fail("sources: expected at most 1000 sources.")
    if verification["status"] in ("verified", "observed") and not sources:
        fail("Verified or observed findings require sources.")
    for source in sources:
        shape(source, {"ref", "platform", "quote", "title", "accessedAt"}, {"timestamp", "revision", "location", "discoveredVia", "verification"})
        for key, item in source.items():
            if key == "verification":
                shape(item, {"status", "method", "at"})
                if not isinstance(item["status"], str) or item["status"] not in VERIFICATION:
                    fail("Invalid source verification status.")
                text(item["method"], "source.verification.method", 4000, False)
                text(item["at"], "source.verification.at", 100, False)
                continue
            text(item, "source." + key, 200_000 if key == "quote" else 4000,
                 empty=key not in ("ref", "platform", "accessedAt"))
    shape(value["refs"], REFS)
    for key, items in value["refs"].items():
        strings(items, key, ids=True)
    return value


def edge(value):
    shape(value, EDGE)
    identifier(value["fromId"]); identifier(value["toId"])
    text(value["relation"], "relation", 30)
    if value["fromId"] == value["toId"] or value["relation"] not in RELATIONS:
        fail("Edge requires distinct endpoints and a supported relation.")
    text(value["reason"], "reason", 10000, False)
    for field in ("resolved", "missing"):
        text(value[field], field, 10000, value["relation"] not in ("continues_to", "resolves"))
    strings(value["evidenceIds"], "evidenceIds", ids=True)
    return value


def header(value):
    return {**{k: v for k, v in value.items() if k not in ("content", "sources")},
            "platforms": sorted({s["platform"] for s in value["sources"]}), "sourceCount": len(value["sources"])}
