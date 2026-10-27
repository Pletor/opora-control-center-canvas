"""Strict additive input, resolved IDs, layout and three-way anchor preconditions."""
from copy import deepcopy

from backend.canvas.architecture_graph import split
from backend.canvas.canvas_plan_build import build
from backend.canvas.canvas_plan_layout import layout
from backend.canvas.graph import digest, validate_graph
from backend.editor.node.node_specs import EMPTY_FIELDS

NODE_KEYS = {"ref", "kind", "name", "parent", "purpose", "size", "position", "sourceRef", "spec", "memberOf"}


def validate_plan(plan):
    if not isinstance(plan, dict) or not set(plan) <= {"nodes", "edges"}:
        raise ValueError("Graph proposals support only additive nodes and edges.")
    if any(not isinstance(plan.get(key, []), list) for key in ("nodes", "edges")):
        raise ValueError("Graph nodes and edges must be lists.")
    for node in plan.get("nodes", []):
        if not isinstance(node, dict) or not set(node) <= NODE_KEYS or node.get("kind") not in ("node", "sector", "area"):
            raise ValueError("Unsupported graph addition fields or kind.")
    for edge in plan.get("edges", []):
        if not isinstance(edge, dict) or not set(edge) <= {"from", "to", "port", "carries"} or edge.get("port", "next") != "next":
            raise ValueError("Only plain next edges (optionally with carries) are supported.")


def place(additions, base, inside, positions):
    original = deepcopy(base["nodes"])
    existing = deepcopy(original)
    if layout(additions["nodes"], existing, inside, positions) is not None or existing != original:
        raise ValueError("Additions must fit without moving or resizing existing cards.")
    for node in additions["nodes"]:
        node["x"], node["y"] = round(node["x"]), round(node["y"])


def merge(base, additions):
    for key in ("nodes", "edges"):
        ids = {item["id"] for item in base[key]}
        if any(item["id"] in ids for item in additions[key]):
            raise ValueError("Proposed graph identity is already occupied.")
    result = {key: [*deepcopy(base[key]), *deepcopy(additions[key])] for key in ("nodes", "edges")}
    validate_graph(result)
    return result


def semantic(node):
    return {key: value for key, value in node.items() if key not in ("x", "y")}


def anchors(base, additions, inside):
    existing = {node["id"]: node for node in base["nodes"]}
    relevant = set(inside.values()) | {node["parentId"] for node in additions["nodes"]}
    relevant.update(node.get("memberOf") for node in additions["nodes"])
    relevant |= {edge[key] for edge in additions["edges"] for key in ("source", "target")}
    pending, observed = list(relevant), {}
    while pending:
        key = pending.pop()
        if key in existing and key not in observed:
            observed[key] = semantic(existing[key])
            pending.append(existing[key]["parentId"])
    return observed


def check_anchors(expected, graph):
    current = {item["id"]: semantic(item) for item in graph["nodes"]}
    if any(current.get(key) != value for key, value in expected.items()):
        raise ValueError("An existing graph anchor changed or is absent from accepted context.")


def prepare(plan, graph, state):
    validate_plan(plan)
    built = build(plan, graph, state)
    additions = {"nodes": deepcopy(built.nodes), "edges": deepcopy(built.edges)}
    place(additions, graph, built.inside, built.positions)
    merge(graph, additions)
    return {"additions": additions, "refs": built.refs, "inside": built.inside, "positions": built.positions,
            "anchors": anchors(graph, additions, built.inside),
            "specifications": [{"nodeId": node["id"], "fields": built.specs.get(node["id"], dict(EMPTY_FIELDS))}
                               for node in additions["nodes"]]}


def validate_application(service, project, workspace, base, proposal, accepted):
    check_anchors(proposal["anchors"], base)
    if accepted is not None:
        check_anchors(proposal["anchors"], accepted)
    combined = merge(base, proposal["additions"])
    if split(combined)[0] != split(base)[0]:
        raise ValueError("Graph additions cannot mutate shared architecture.")
    service._verify_source_refs(project, workspace, base, combined)
    approved = merge(accepted, proposal["additions"]) if accepted is not None else combined
    from backend.canvas.opora_graph_addition_safety import validate_additions
    validate_additions(service, project, workspace, base, combined, accepted if accepted is not None else base, approved)
    return combined


def unchanged_specifications(accepted, live):
    by_id = {item["nodeId"]: item for item in live}
    if any(by_id.get(item["nodeId"]) != item for item in accepted):
        raise ValueError("Existing accepted specifications differ from working documents.")
    known = {item["nodeId"] for item in accepted}
    return [deepcopy(item) for item in live if item["nodeId"] not in known]


def graph_digest(graph):
    return digest(graph)
