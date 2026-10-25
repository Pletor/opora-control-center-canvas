"""Review triples and exact affected-field preconditions for explicit rebases."""
from copy import deepcopy

from backend.canvas.areas import area_of
from backend.canvas.opora_graph_build import semantic


def changes(accepted, working, approved, result, plan, additions):
    review = {}
    for kind in ("nodes", "edges"):
        maps = [{item["id"]: item for item in graph[kind]} for graph in (accepted, working, approved, result)]
        operations = {item["id"]: ("update", sorted(item["fields"]) if kind == "nodes" else ["source", "target", "port"])
                      for item in plan[f"update{kind.title()}"]}
        operations.update({key: ("remove", []) for key in plan[f"remove{kind.title()}"]})
        operations.update({item["id"]: ("add", sorted(item)) for item in additions[kind]})
        review[kind] = [{"id": key, "operation": operation, "fields": fields,
                         **{name: deepcopy(mapping.get(key)) for name, mapping in zip(
                             ("acceptedBefore", "workingBefore", "proposedAccepted", "proposedWorking"), maps, strict=True)}}
                        for key, (operation, fields) in sorted(operations.items())]
    memberships = []
    maps = []
    for graph in (accepted, working, approved, result):
        mapping = {}
        for node in graph["nodes"]:
            area = area_of(node, graph["nodes"])
            mapping[node["id"]] = area["id"] if area else None
        maps.append(mapping)
    for key in sorted(set(maps[0]) | set(maps[1])):
        values = [mapping.get(key) for mapping in maps]
        if values[0] != values[2] or values[1] != values[3]:
            memberships.append({"id": key, **dict(zip(
                ("acceptedBefore", "workingBefore", "proposedAccepted", "proposedWorking"), values, strict=True))})
    return {**review, "areaMembership": memberships}


def preconditions(graph, plan, additions, inside=None):
    """Field patches permit unrelated edits; removals bind whole entities and exact closure."""
    observed = {}
    nodes = {item["id"]: item for item in graph["nodes"]}
    relevant = set((inside or {}).values())
    for kind in ("nodes", "edges"):
        mapping = {item["id"]: item for item in graph[kind]}
        observed[kind] = {}
        for update in plan[f"update{kind.title()}"]:
            before = mapping.get(update["id"])
            fields = update["fields"] if kind == "nodes" else ("source", "target", "port")
            observed[kind][update["id"]] = None if before is None else {
                key: {"present": key in before, "value": deepcopy(before.get(key))} for key in fields}
            if kind == "nodes" and before:
                observed[kind][update["id"]]["$kind"] = before["kind"]
                area = area_of(before, graph["nodes"])
                observed[kind][update["id"]]["$areaId"] = area["id"] if area else None
                relevant.add(before.get("parentId"))
                relevant.add(update["fields"].get("parentId"))
                relevant.add(before.get("memberOf"))
                relevant.add(update["fields"].get("memberOf"))
            elif before:
                relevant.update(before[key] for key in ("source", "target"))
                relevant.update(update[key] for key in ("source", "target"))
        for key in plan[f"remove{kind.title()}"]:
            observed[kind][key] = deepcopy(mapping.get(key))
    removed = set(plan["removeNodes"])
    observed["closure"] = {"children": sorted(node["id"] for node in graph["nodes"] if node.get("parentId") in removed),
                           "edges": sorted(edge["id"] for edge in graph["edges"]
                                           if edge["source"] in removed or edge["target"] in removed)}
    relevant.update(node.get("parentId") for node in additions["nodes"])
    relevant.update(node.get("memberOf") for node in additions["nodes"])
    relevant.update(edge[key] for edge in additions["edges"] for key in ("source", "target"))
    anchors, pending = {}, list(relevant)
    while pending:
        key = pending.pop()
        if key not in nodes or key in anchors:
            continue
        anchors[key] = deepcopy(semantic(nodes[key]))
        pending.append(nodes[key].get("parentId"))
    observed["anchors"] = anchors
    return observed
