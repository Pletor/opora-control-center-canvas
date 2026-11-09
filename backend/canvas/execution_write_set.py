"""Explicit affected elements belong to one accepted task, never new tickets."""
import re


def affected_ids(fields):
    value = fields.get("affectedNodeIds", [])
    if (not isinstance(value, list) or not 1 <= len(value) <= 50
            or any(not isinstance(item, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", item) for item in value)
            or len(set(value)) != len(value)):
        if "affectedNodeIds" in fields:
            raise ValueError("affectedNodeIds requires 1–50 unique element identities.")
    return sorted(value)


def resolve_affected(node, fields, graph, documents):
    identifiers = affected_ids(fields)
    nodes = {item["id"]: item for item in graph["nodes"]}
    docs = {item["nodeId"]: item for item in documents}
    for identifier in identifiers:
        if identifier == node or nodes.get(identifier, {}).get("kind") not in ("node", "sector") or identifier not in docs:
            raise ValueError("Affected elements must be distinct existing accepted nodes or sectors.")
    return identifiers
