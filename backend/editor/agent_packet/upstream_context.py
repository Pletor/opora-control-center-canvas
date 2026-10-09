"""Explicit provenance of direct incoming decisions and handoffs."""

from backend.editor.agent_packet.desktop_v3_packets import redact_deep


def upstream_context(graph, state, node_id):
    by_id = {node["id"]: node for node in graph["nodes"]}
    result = []
    for edge in graph["edges"]:
        if edge["target"] != node_id or edge["source"] not in by_id or edge.get("port") == "flow":
            continue
        source = by_id[edge["source"]]
        ports = [{"blockId": block["id"], **port}
                 for block in state["nodes"].get(source["id"], {}).get("blocks", [])
                 for port in block.get("ports", [])]
        source_port = next((port for port in ports if port["blockId"] == edge.get("sourceBlockId")
                            and port["id"] == edge.get("sourcePortId")), None)
        result.append({"edgeId": edge["id"], "nodeId": source["id"], "name": source["name"],
                       "assumptionChanged": any(d.get("supersedes") and d.get("nodeId") == source["id"] for d in state.get("decisions", [])),
                       "sourcePort": source_port, "chosenPorts": [p for p in ports if p.get("status") == "chosen"],
                       "decisions": [d for d in state.get("decisions", []) if d.get("nodeId") == source["id"]],
                       "report": state.get("edges", {}).get(edge["id"])})
    return redact_deep(result)
