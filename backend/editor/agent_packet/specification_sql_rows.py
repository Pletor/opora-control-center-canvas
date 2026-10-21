"""Strict private SQL snapshot decoding; no database or file reads."""
import json

from backend.canvas.architecture_graph import EMPTY_REMOVED, check_shape, compose
from backend.canvas.graph import EMPTY, valid_id, validate_graph
from database.repositories.opora_context_events_sources import SOURCES
from database.repositories.workspace_graph_authority import _encode


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("Duplicate JSON key in SQL context.")
        result[key] = value
    return result


def decode(raw):
    if not isinstance(raw, str):
        raise TypeError("SQL JSON must be text.")
    try:
        return json.loads(raw, object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
    except (RecursionError, UnicodeError) as error:
        raise ValueError("Invalid SQL context JSON.") from error


def validate_rows(rows, project):
    if not isinstance(rows, dict) or set(rows) != set(SOURCES):
        raise ValueError("All SQL context sources are required.")
    count = 0
    for table, columns in SOURCES.items():
        if not isinstance(rows[table], list):
            raise TypeError("Invalid SQL source rows.")
        seen = set()
        for row in rows[table]:
            count += 1
            if not isinstance(row, dict) or set(row) != set(columns) or row["project_id"] != project:
                raise ValueError("Invalid SQL source scope or columns.")
            for key, value in row.items():
                if key == "revision":
                    if type(value) is not int or value < 1:
                        raise ValueError("Invalid SQL revision.")
                elif not isinstance(value, str):
                    raise ValueError("Invalid SQL source value.")
            identity = tuple(row[key] for key in columns if key.endswith("_id"))
            if table.endswith("_revisions"):
                identity += (row["revision"],)
            if identity in seen:
                raise ValueError("Duplicate SQL source row.")
            seen.add(identity)
    try:
        size = len(json.dumps(rows, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise ValueError("Invalid SQL snapshot.") from error
    if count > 8192 or size > 8 * 1024 * 1024:
        raise ValueError("SQL snapshot exceeds context bounds.")


def latest(rows, table, **owner):
    matches = [row for row in rows[table] if all(row[key] == value for key, value in owner.items())]
    return max(matches, key=lambda row: row.get("revision", 0), default=None)


def composed_graph(rows, workspace):
    authority = latest(rows, "workspace_graph_authority", workspace_id=workspace)
    if authority is None:
        raise ValueError("SQL graph authority is required; fallback is forbidden.")
    content = decode(authority["graph"])
    raw, fingerprint = _encode(content)
    if raw != authority["graph"] or fingerprint != authority["digest"]:
        raise ValueError("SQL graph authority integrity failed.")
    arch = latest(rows, "project_architecture")
    architecture = decode(arch["graph"]) if arch else dict(EMPTY)
    check_shape(architecture)
    if set(architecture) != {"nodes", "edges"}:
        raise ValueError("Invalid architecture graph fields.")
    # Validate uniqueness before composition, which otherwise hides duplicate twins.
    for collection in ("nodes", "edges"):
        ids = [item["id"] for item in architecture[collection]]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate architecture identifier.")
    removed = decode(arch["removed"]) if arch else dict(EMPTY_REMOVED)
    if (not isinstance(removed, dict) or set(removed) != {"nodes", "edges"}
            or any(not isinstance(value, list) or not all(valid_id(x) for x in value)
                   or len(value) != len(set(value)) for value in removed.values())):
        raise ValueError("Invalid removed architecture identifiers.")
    architecture_edges = {edge["id"]: edge for edge in architecture["edges"]}
    if any(edge["id"] in architecture_edges and edge != architecture_edges[edge["id"]]
           for edge in content["edges"]):
        raise ValueError("Conflicting architecture edge.")
    graph, conflicts = compose(architecture, removed, content)
    if conflicts:
        raise ValueError("Conflicting SQL graph architecture.")
    validate_graph(graph)
    return graph, {node["id"] for node in architecture["nodes"]}
