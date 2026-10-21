"""Check stable server identities still describe the exact submitted additive plan."""
from copy import deepcopy

from backend.canvas.canvas_plan_build import build
from backend.canvas.opora_graph_change_plan import apply
from backend.editor.node.node_specs import EMPTY_FIELDS


def validate_origin(record):
    plan = {key: record["plan"][key] for key in ("nodes", "edges")}
    if not any(plan.values()):
        if any(record["additions"].values()) or any(record[key] for key in ("refs", "inside", "positions", "specifications")):
            raise ValueError("Graph changes contain unrequested additions.")
        return
    built = build(plan, apply(record["baseGraph"], record["plan"]), {"nodes": {}})
    if set(built.refs) != set(record["refs"]) or len(set(record["refs"].values())) != len(record["refs"]):
        raise ValueError("Graph addition reference identity mismatch.")
    translate = {value: record["refs"][key] for key, value in built.refs.items()}
    if len(built.edges) != len(record["additions"]["edges"]):
        raise ValueError("Graph addition edge count mismatch.")
    translate.update({edge["id"]: saved["id"] for edge, saved in zip(built.edges, record["additions"]["edges"], strict=True)})
    nodes, edges = deepcopy(built.nodes), deepcopy(built.edges)
    for node in nodes:
        node["id"] = translate[node["id"]]
        node["parentId"] = translate.get(node["parentId"], node["parentId"])
    for edge in edges:
        for key in ("id", "source", "target"):
            edge[key] = translate.get(edge[key], edge[key])
    def without_coordinates(items):
        return [{key: value for key, value in item.items() if key not in ("x", "y")} for item in items]
    if without_coordinates(nodes) != without_coordinates(record["additions"]["nodes"]) or edges != record["additions"]["edges"]:
        raise ValueError("Persisted additions differ from their explicit plan.")
    inside = {translate[key]: translate.get(value, value) for key, value in built.inside.items()}
    positions = {translate[key]: value for key, value in built.positions.items()}
    specs = [{"nodeId": translate[node["id"]], "fields": built.specs.get(node["id"], dict(EMPTY_FIELDS))} for node in built.nodes]
    if inside != record["inside"] or positions != record["positions"] or specs != record["specifications"]:
        raise ValueError("Graph addition placement or specifications differ from their plan.")
