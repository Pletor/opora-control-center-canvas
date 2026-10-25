"""Strict immutable selection claims, not attestations of quality or permissions.

Only called after validating the kit resources. The accepted assignment pins these
claims; their shape and resource binding never make their evidence authoritative.
"""
import hashlib
import json
import re

REASONS = {"explicit-assignment", "baseline-policy", "native-stable", "observed-outcomes",
           "shared-fixture-exploration", "unknown-exploration", "inherited-settings"}
SCOPES = {"global", "repository", "page", "layer", "area", "sector", "task"}
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@/+\-]{0,199}\Z")
NODE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@/%+\-]{0,1023}\Z")


def _keys(value, keys):
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("Harness selection has unexpected or missing fields.")


def _id(value):
    return isinstance(value, str) and ID.fullmatch(value) is not None


def _safe_integer(value):
    # JSON has one numeric type: JS parses 3 and 3.0 identically. Preserve the
    # value, but reject booleans, fractions, infinities and integers beyond JS safety.
    return type(value) in (int, float) and 0 <= value <= 9007199254740991 and value == int(value)


def version_digest(resource):
    value = {key: resource[key] for key in ("resource", "category", "digest", "requires")}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=True).encode()).hexdigest()


def validate_selection(kit):
    selection = kit["selection"]
    _keys(selection, {"schema", "policy", "problem", "profileRevision", "declaredCapabilities",
                      "evidence", "entries"})
    if (selection["schema"] != "harness.selection/1" or selection["policy"] != "harness.recommendation/1"
            or selection["evidence"] != "caller-declared-selection"
            or selection["problem"] not in kit["problems"]):
        raise ValueError("Invalid Harness selection schema, policy, evidence or problem.")
    revision = selection["profileRevision"]
    if revision is not None and not _safe_integer(revision):
        raise ValueError("Invalid Harness selection profile revision.")
    capabilities = selection["declaredCapabilities"]
    if (not isinstance(capabilities, list) or len(capabilities) > 32
            or not all(_id(item) for item in capabilities) or len(set(capabilities)) != len(capabilities)):
        raise ValueError("Invalid Harness selection declared capabilities.")
    entries = selection["entries"]
    if not isinstance(entries, list) or len(entries) != len(kit["resources"]):
        raise ValueError("Harness selection must cover every resource in order.")
    for order, (entry, resource) in enumerate(zip(entries, kit["resources"])):
        _keys(entry, {"resource", "digest", "versionDigest", "order", "reason", "assignments"})
        if (entry["resource"] != resource["resource"] or entry["digest"] != resource["digest"]
                or entry["versionDigest"] != version_digest(resource)
                or not _safe_integer(entry["order"]) or entry["order"] != order
                or not isinstance(entry["reason"], str) or entry["reason"] not in REASONS):
            raise ValueError("Harness selection does not match the exact ordered resource version.")
        assignments = entry["assignments"]
        if not isinstance(assignments, list) or len(assignments) > 32:
            raise ValueError("Invalid Harness selection assignment origins.")
        if (entry["reason"] == "explicit-assignment") != bool(assignments):
            raise ValueError("Only explicit Harness selection has assignment origins.")
        seen = set()
        for origin in assignments:
            _keys(origin, {"slot", "scope", "node"})
            scope, node, slot = origin["scope"], origin["node"], origin["slot"]
            if not _id(slot) or not isinstance(scope, str) or scope not in SCOPES or slot in seen:
                raise ValueError("Invalid or duplicate Harness selection origin.")
            if node is not None and (not isinstance(node, str) or NODE.fullmatch(node) is None
                                     or scope in {"global", "repository"}):
                raise ValueError("Invalid Harness selection origin node.")
            seen.add(slot)
        if assignments and revision is None:
            raise ValueError("Explicit selection needs a profile revision.")
        settings = resource["resource"] == "profile:settings"
        if settings != (entry["reason"] == "inherited-settings"):
            raise ValueError("Generated settings need their own selection reason.")
        if settings and (resource["slot"] != "settings.profile" or resource["category"] != "instructions"
                         or resource["requires"]):
            raise ValueError("Invalid generated settings resource.")
        if entry["reason"] == "baseline-policy" and resource["resource"] not in {"guide:instructions", "guide:testing"}:
            raise ValueError("Invalid baseline selection resource.")
