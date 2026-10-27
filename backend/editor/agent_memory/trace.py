"""Dohledatelnost podle ID: co entita je, komu patří a odkud/kam vedou větve nebo vazby.

Počítá se čistě z uloženého stavu Desktop v3 a grafu; žádný běh, žádný odhad. Pořadí odkazů
je pořadí zápisu (uzly grafu, pak bloky v pořadí uložení), aby odpověď byla deterministická.
"""


def _blocks(state):
    for node_id, node in state["nodes"].items():
        for block in node.get("blocks", []):
            yield node_id, block


def _label_of(state, by_id, kind, target):
    if kind == "node":
        return by_id[target]["name"] if target in by_id else target
    for _node_id, block in _blocks(state):
        if kind == "block" and block["id"] == target:
            return block["title"]
    for node in state["nodes"].values():
        for action in node.get("actions", []):
            if kind == "action" and action["id"] == target:
                return action["label"]
    return target


def _incoming(state, by_id, kind, target):
    """Větve bloků, které míří na entitu (target) daného druhu."""
    found = []
    for _node_id, block in _blocks(state):
        for via in ("onMet", "onUnmet"):
            branch = block["state"][via]
            if branch["kind"] == kind and branch["targetId"] == target:
                found.append({"via": via, "kind": "block", "sourceId": block["id"], "label": block["title"]})
    return found


def _outgoing(state, by_id, block):
    found = []
    for via in ("onMet", "onUnmet"):
        branch = block["state"][via]
        if branch["kind"] != "none":
            found.append({"via": via, "kind": branch["kind"], "targetId": branch["targetId"],
                          "label": _label_of(state, by_id, branch["kind"], branch["targetId"])})
    return found


def _carries(edge):
    """Druh toku vazby jen tam, kde ho graf nese (`docs/architektura-pro-agenty.md` §3.4)."""
    return {"carries": edge["carries"]} if "carries" in edge else {}


def trace(state, graph, entity_id):
    by_id = {item["id"]: item for item in graph["nodes"]}
    if entity_id in by_id:
        node = by_id[entity_id]
        incoming = [
            {"via": "edge", "kind": "node", "sourceId": edge["source"], "label": by_id[edge["source"]]["name"], "port": edge.get("port", "next"), **_carries(edge)}
            for edge in graph["edges"] if edge["target"] == entity_id and edge["source"] in by_id
        ] + _incoming(state, by_id, "node", entity_id)
        outgoing = [
            {"via": "edge", "kind": "node", "targetId": edge["target"], "label": by_id[edge["target"]]["name"], "port": edge.get("port", "next"), **_carries(edge)}
            for edge in graph["edges"] if edge["source"] == entity_id and edge["target"] in by_id
        ]
        return {"id": entity_id, "kind": "node", "nodeId": entity_id, "label": node["name"], "nodeKind": node["kind"],
                "incoming": incoming, "outgoing": outgoing}
    for edge in graph["edges"]:
        if edge["id"] == entity_id:
            return {"id": entity_id, "kind": "edge", "source": edge["source"], "target": edge["target"], "port": edge.get("port", "next"), **_carries(edge)}
    for node_id, block in _blocks(state):
        if block["id"] == entity_id:
            return {"id": entity_id, "kind": "block", "nodeId": node_id, "blockId": block["id"], "number": block["number"],
                    "label": block["title"], "parentBlockId": block["parentBlockId"],
                    "incoming": _incoming(state, by_id, "block", entity_id), "outgoing": _outgoing(state, by_id, block)}
        for todo in block["todos"]:
            if todo["id"] == entity_id:
                return {"id": entity_id, "kind": "todo", "nodeId": node_id, "blockId": block["id"], "label": todo["text"], "done": todo["done"]}
        for image in block["images"]:
            if image["id"] == entity_id:
                return {"id": entity_id, "kind": "image", "nodeId": node_id, "blockId": block["id"], "path": image["path"]}
    for node_id, node in state["nodes"].items():
        for action in node.get("actions", []):
            if action["id"] == entity_id:
                return {"id": entity_id, "kind": "action", "nodeId": node_id, "label": action["label"], "pipelineId": action["pipelineId"],
                        "incoming": _incoming(state, by_id, "action", entity_id)}
        for rule in node.get("rules", []):
            if rule["id"] == entity_id:
                return {"id": entity_id, "kind": "rule", "nodeId": node_id, "label": rule["text"], "ruleKind": rule["kind"]}
    return None
