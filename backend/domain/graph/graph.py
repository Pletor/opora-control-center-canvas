import hashlib
import json
import math
import re

from backend.integrations.workspace_sources import relative_path

EMPTY = {"nodes": [], "edges": []}
NODE_KEYS = {"id", "parentId", "kind", "name", "purpose", "x", "y"}
NODE_KEYS_WITH_SOURCE = NODE_KEYS | {"sourceRef"}


def valid_id(value):
    return isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value))


def validate_source_ref(ref, kind):
    """Ověří tvar odkazu na skutečný nebo navrhovaný zdroj; nesahá na disk."""
    if ref is None:
        return
    if not isinstance(ref, dict) or set(ref) != {"origin", "path", "kind"}:
        raise ValueError("Neplatný odkaz na zdroj.")
    if ref["origin"] not in ("existing", "planned"):
        raise ValueError("Neplatný typ odkazu na zdroj.")
    if ref["kind"] not in ("directory", "file"):
        raise ValueError("Neplatný druh zdroje.")
    if kind == "sector" and ref["kind"] != "directory":
        raise ValueError("Sektor může mít jen adresářový zdroj.")
    try:
        relative_path(ref["path"])
    except ValueError:
        raise ValueError("Neplatná cesta zdroje.")
    if kind == "node" and ref["origin"] == "existing" and ref["path"] == "":
        raise ValueError("Uzel musí odkazovat na potomka sektoru, ne na kořen.")


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
    sources = {}
    for n in nodes:
        if not isinstance(n, dict) or set(n) not in (NODE_KEYS, NODE_KEYS_WITH_SOURCE):
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
        source_ref = n.get("sourceRef") if "sourceRef" in n else None
        validate_source_ref(source_ref, n["kind"])
        if (
            n["kind"] == "sector"
            and source_ref
            and source_ref["origin"] == "planned"
            and len(n["purpose"].strip()) < 12
        ):
            raise ValueError("Návrh sektoru vyžaduje smysluplnou podstatu.")
        sources[n["id"]] = source_ref
        ids.add(n["id"])
    parents = {n["id"]: n["parentId"] for n in nodes}
    kinds = {n["id"]: n["kind"] for n in nodes}
    for key in ids:
        seen = set()
        current = key
        while current is not None:
            if current not in ids or current in seen:
                raise ValueError("Graf má cyklus nebo chybějícího rodiče.")
            seen.add(current)
            current = parents[current]
    for node_id, source_ref in sources.items():
        if source_ref is None or kinds[node_id] != "node":
            continue
        cursor = parents[node_id]
        has_sector = False
        while cursor is not None:
            if kinds[cursor] == "sector":
                has_sector = True
                break
            cursor = parents[cursor]
        if not has_sector:
            raise ValueError("Uzel se zdrojem musí ležet uvnitř sektoru.")
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
