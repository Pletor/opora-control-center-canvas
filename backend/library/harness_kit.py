"""Bounded, content-addressed tools in an accepted specification, never permission grants.

The existing specification acceptance and sparse context machinery owns persistence,
lineage, source coverage and replay. This module performs no file/network/process I/O.
"""
import hashlib
import json
import re

from backend.library.harness_selection import validate_selection

SCHEMA = "harness.kit/1"
SUPPORTED_SCHEMAS = (SCHEMA, "harness.kit/2")
CATEGORIES = {"instructions", "skills", "hooks", "rules", "commands", "scripts", "tools",
              "mcp", "memory", "plugins", "permissions", "testing", "operations"}
MAX_BYTES = 96 * 1024
MAX_RESOURCES = 24
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@/+-]{0,199}\Z")
SLOT = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,79}\Z")


def _keys(value, required):
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("Harness kit has unexpected or missing fields.")


def _identifier(value):
    return isinstance(value, str) and IDENTIFIER.fullmatch(value) is not None


def validate_kit(value):
    """Validate exact data without truncating IDs, rewriting content or trusting claims.

    A digest identifies UTF-8 content. Metadata and ordering are additionally pinned by
    the accepted assignment digest. Requires are requirements, not installed capabilities.
    Empty resource sets explicitly pin an empty kit; absence preserves legacy behavior.
    """
    v2 = isinstance(value, dict) and value.get("schema") == "harness.kit/2"
    _keys(value, {"schema", "problems", "resources", "selection"} if v2 else {"schema", "problems", "resources"})
    if value["schema"] not in SUPPORTED_SCHEMAS:
        raise ValueError("Unsupported Harness kit schema.")
    problems, resources = value["problems"], value["resources"]
    if (not isinstance(problems, list) or not 1 <= len(problems) <= 8
            or not all(_identifier(item) for item in problems) or len(set(problems)) != len(problems)):
        raise ValueError("Harness kit needs 1-8 distinct problem identifiers.")
    if not isinstance(resources, list) or len(resources) > MAX_RESOURCES:
        raise ValueError("Harness kit exceeds 24 resources.")
    slots, identities = set(), set()
    for entry in resources:
        _keys(entry, {"slot", "resource", "category", "digest", "content", "requires"})
        slot, resource = entry["slot"], entry["resource"]
        if (not isinstance(slot, str) or not SLOT.fullmatch(slot)
                or slot in {"__proto__", "prototype", "constructor"} or not _identifier(resource)):
            raise ValueError("Invalid Harness resource slot or identity.")
        if slot in slots or resource in identities:
            raise ValueError("Harness kit contains a duplicate slot or resource.")
        slots.add(slot)
        identities.add(resource)
        category, content, required = entry["category"], entry["content"], entry["requires"]
        if not isinstance(category, str) or category not in CATEGORIES:
            raise ValueError("Invalid Harness resource category.")
        if (not isinstance(content, str) or len(content) > MAX_BYTES or "\0" in content):
            raise ValueError("Invalid or oversized Harness resource content.")
        try:
            actual = hashlib.sha256(content.encode("utf-8")).hexdigest()
        except UnicodeError as error:
            raise ValueError("Harness resource content is not valid UTF-8.") from error
        if entry["digest"] != actual:
            raise ValueError("Harness resource SHA-256 does not match its exact content.")
        if (not isinstance(required, list) or len(required) > 16
                or not all(_identifier(item) for item in required) or len(set(required)) != len(required)):
            raise ValueError("Invalid Harness capability requirements.")
    if v2:
        validate_selection(value)
    # Limit the complete representation, not just individual resource content.
    encoded = json.dumps(value, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    if len(encoded.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Harness kit exceeds 96 KiB including metadata.")


def kit_of_assignment(assignment, node_id):
    """Read only the target's already-pinned kit, never a neighbor's or live library.

    Caller owns execution authentication and assignment integrity. Return None for an
    old assignment. Validate after redaction too: changed content cannot retain a digest.
    """
    documents = assignment.get("documents", [])
    targets = [doc for doc in documents if doc.get("nodeId") == node_id]
    if len(targets) > 1:
        raise ValueError("Ambiguous target Harness specification.")
    fields = targets[0].get("fields", {}) if targets else {}
    if "harness" not in fields:
        return None
    kit = fields["harness"]
    validate_kit(kit)
    return kit


class KitContextRequired(ValueError):
    """The card is claimable, but only through the sparse (v2) execution context."""


def require_kit_context(fields, version):
    if "harness" in fields and version != 2:
        raise KitContextRequired("Harness kits require contextProtocolVersion 2; prepare and claim the sparse context.")
