"""Explicit graph patch input; no inferred deletion or working-graph adoption."""

from copy import deepcopy

from backend.canvas.graph import valid_id
from backend.canvas.opora_graph_build import validate_plan

FIELDS = {"name", "purpose", "parentId", "sourceRef", "x", "y", "size"}
EDIT_KEYS = {"updateNodes", "removeNodes", "updateEdges", "removeEdges"}


def normalize(plan):
    if not isinstance(plan, dict) or not set(plan) <= EDIT_KEYS | {"nodes", "edges", "adoptArchitectureContext"}:
        raise ValueError("Invalid graph change plan fields.")
    result = {key: deepcopy(plan.get(key, [])) for key in sorted(EDIT_KEYS | {"nodes", "edges"})}
    if any(not isinstance(value, list) for value in result.values()):
        raise ValueError("Graph operations must be lists.")
    if type(plan.get("adoptArchitectureContext", False)) is not bool:
        raise ValueError("Architecture context adoption must be an explicit boolean.")
    if (not any(result.values()) and not plan.get("adoptArchitectureContext")) or sum(map(len, result.values())) > 6000:
        raise ValueError("Graph change operations are empty or exceed limits.")
    validate_plan({key: result[key] for key in ("nodes", "edges")})
    for key in ("updateNodes", "updateEdges"):
        for item in result[key]:
            required = {"id", "fields"} if key == "updateNodes" else {"id", "source", "target", "port"}
            if not isinstance(item, dict) or set(item) != required or not valid_id(item["id"]):
                raise ValueError("Invalid graph update fields or identity.")
            if key == "updateNodes":
                fields = item["fields"]
                if not isinstance(fields, dict) or not fields or not set(fields) <= FIELDS:
                    raise ValueError("Unsupported or empty node field patch.")
                if "parentId" in fields and fields["parentId"] is not None and not valid_id(fields["parentId"]):
                    raise ValueError("Parent references must be existing node identities.")
            elif item["port"] != "next" or not all(valid_id(item[field]) for field in ("source", "target")):
                raise ValueError("Only plain next edge updates with existing references are supported.")
    for kind in ("Nodes", "Edges"):
        remove, update = result[f"remove{kind}"], result[f"update{kind}"]
        if any(not valid_id(item) for item in remove):
            raise ValueError("Invalid removal identity.")
        ids = [*remove, *(item["id"] for item in update)]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate or conflicting graph operations.")
    return {**result, "adoptArchitectureContext": plan.get("adoptArchitectureContext", False)}


def apply(graph, plan):
    result = deepcopy(graph)
    for kind in ("nodes", "edges"):
        suffix = kind.title()
        indexed = {item["id"]: item for item in result[kind]}
        for update in plan[f"update{suffix}"]:
            target = indexed.get(update["id"])
            if target is None:
                raise ValueError("Updated graph identity is absent from accepted or working context.")
            if kind == "nodes" and target["kind"] not in ("node", "sector", "area"):
                raise ValueError("Shared architecture and special nodes cannot be edited.")
            if kind == "edges" and target.get("port", "next") != "next":
                raise ValueError("Only plain next edges can be updated.")
            fields = update["fields"] if kind == "nodes" else {key: update[key] for key in ("source", "target", "port")}
            for key, value in fields.items():
                if kind == "edges" and key == "port" and target.get("port", "next") == value:
                    continue
                if key in ("sourceRef", "size") and value is None:
                    target.pop(key, None)
                else:
                    target[key] = deepcopy(value)
        removed = set(plan[f"remove{suffix}"])
        if kind == "edges" and any(item["id"] in removed and item.get("port", "next") != "next" for item in result[kind]):
            raise ValueError("Only plain next edges can be removed.")
        if kind == "nodes":
            if any(item["id"] in removed and item["kind"] not in ("node", "sector", "area") for item in result[kind]):
                raise ValueError("Shared architecture and special nodes cannot be removed.")
            missing = {item["id"] for item in result[kind] if item.get("parentId") in removed and item["id"] not in removed}
            if missing:
                raise ValueError(f"Explicit descendant removals required: {', '.join(sorted(missing))}")
        result[kind] = [item for item in result[kind] if item["id"] not in removed]
    removed = set(plan["removeNodes"])
    incident = {edge["id"] for edge in result["edges"] if edge["source"] in removed or edge["target"] in removed}
    if incident:
        raise ValueError(f"Explicit incident edge removals required: {', '.join(sorted(incident))}")
    return result


def validate_targets(accepted, working, plan):
    for kind in ("nodes", "edges"):
        ids = {item["id"] for graph in (accepted, working) for item in graph[kind]}
        if any(item not in ids for item in plan[f"remove{kind.title()}"]):
            raise ValueError("Removed identity is absent from both accepted and working graphs.")
    for graph in (accepted, working):
        ids = {item["id"] for item in graph["nodes"]}
        refs = {item["fields"]["parentId"] for item in plan["updateNodes"] if "parentId" in item["fields"]}
        refs |= {item[field] for item in plan["updateEdges"] for field in ("source", "target")}
        if not refs - {None} <= ids:
            raise ValueError("Edit references must exist in accepted and working graphs.")
