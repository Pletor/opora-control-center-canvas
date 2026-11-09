"""Pure native removal cleanup, shared by apply and exact review/readback."""
from backend.editor.agent_memory.block_access import _default_branch


def removed_state(state, node_ids, edge_ids):
    nodes, edges = set(node_ids), set(edge_ids)
    def clean(branch):
        return _default_branch() if branch["kind"] == "node" and branch["targetId"] in nodes else branch
    result = {}
    for identifier, node in state["nodes"].items():
        if identifier in nodes:
            continue
        if node.get("blocks"):
            node = {**node, "blocks": [{**b, "state": {**b["state"], "onMet": clean(b["state"]["onMet"]),
                                                            "onUnmet": clean(b["state"]["onUnmet"])}} for b in node["blocks"]]}
        result[identifier] = node
    return {**state, "nodes": result, "edges": {k: v for k, v in state["edges"].items() if k not in edges},
            "rules": [r for r in state["rules"] if not (r["scope"] == "node" and r["target"] in nodes)],
            "decisions": [d for d in state["decisions"] if d["nodeId"] not in nodes]}
