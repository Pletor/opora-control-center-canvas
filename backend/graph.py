import hashlib
import json
import math
import re

EMPTY = {"nodes": [], "edges": []}


def valid_id(value):
    return isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value))


def validate_graph(value):
    if not isinstance(value, dict) or set(value) != {"nodes", "edges"}:
        raise ValueError("Neplatný formát grafu.")
    nodes, edges = value["nodes"], value["edges"]
    if (
        not isinstance(nodes, list)
        or not isinstance(edges, list)
        or len(nodes) > 2000
        or len(edges) > 4000
    ):
        raise ValueError("Graf překročil povolený rozsah.")
    ids = set()
    for n in nodes:
        if not isinstance(n, dict) or set(n) != {
            "id",
            "parentId",
            "kind",
            "name",
            "purpose",
            "x",
            "y",
        }:
            raise ValueError("Neplatný uzel.")
        if not valid_id(n["id"]) or n["id"] in ids or n["kind"] not in ("node", "sector"):
            raise ValueError("Neplatná identita nebo typ uzlu.")
        if (
            not isinstance(n["name"], str)
            or not n["name"].strip()
            or len(n["name"]) > 160
            or not isinstance(n["purpose"], str)
            or len(n["purpose"]) > 12000
        ):
            raise ValueError("Neplatný název nebo podstata.")
        if any(
            type(n[k]) not in (int, float) or not math.isfinite(n[k]) or abs(n[k]) > 1000000
            for k in ("x", "y")
        ):
            raise ValueError("Neplatná pozice.")
        ids.add(n["id"])
    parents = {n["id"]: n["parentId"] for n in nodes}
    for key in ids:
        seen = set()
        current = key
        while current is not None:
            if current not in ids or current in seen:
                raise ValueError("Graf má cyklus nebo chybějícího rodiče.")
            seen.add(current)
            current = parents[current]
    edge_ids = set()
    for edge in edges:
        if (
            not isinstance(edge, dict)
            or set(edge) != {"id", "source", "target"}
            or not valid_id(edge["id"])
            or edge["id"] in edge_ids
            or edge["source"] not in ids
            or edge["target"] not in ids
            or edge["source"] == edge["target"]
        ):
            raise ValueError("Neplatná vazba.")
        edge_ids.add(edge["id"])
    return value


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()
