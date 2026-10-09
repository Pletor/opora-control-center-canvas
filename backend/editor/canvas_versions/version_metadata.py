"""Checkpoint provenance and changed card count, independent of content/CAS tokens."""
from backend.editor.agent_packet.effective_rules import effective_rules


def card_content(graph, state, snapshot):
    result = {}
    for node in graph["nodes"]:
        if node["kind"] not in ("node", "sector"):
            continue
        key = node["id"]
        records = {}
        for name, rows in (snapshot or {}).get("records", {}).items():
            records[name] = [{"key": row["key"], "data": row["data"]} for row in rows
                             if (row["data"].get("node_id") == key if name == "documents" else row["key"][0] == key)]
        result[key] = {"node": node, "state": state.get("nodes", {}).get(key), "records": records,
                       "rules": effective_rules(graph, state, key), "settings": state.get("settings", []),
                       "decisions": [d for d in state.get("decisions", []) if d.get("pinned") or d.get("nodeId") == key],
                       "edges": [e for e in graph["edges"] if key in (e["source"], e["target"])]}
        result[key]["reports"] = {edge["id"]: state.get("edges", {}).get(edge["id"])
                                   for edge in result[key]["edges"]}
        result[key]["uploads"] = [item for item in (snapshot or {}).get("assets", {}).get("uploads", [])
                                  if item["nodeId"] == key]
        drawing_ids = {element.get("fileId") for row in records.get("drawings", [])
                       for element in row["data"]["scene"]["elements"] if element.get("type") == "image"}
        result[key]["drawingAssets"] = [item for item in (snapshot or {}).get("assets", {}).get("drawings", [])
                                        if item["id"] in drawing_ids]
    return result


def changed_cards(graph, state, snapshot, previous):
    current = card_content(graph, state, snapshot)
    if previous is None:
        return len(current)
    if previous[2] is None:
        return None
    before = card_content(*previous)
    return sum(current.get(key) != before.get(key) for key in current.keys() | before.keys())
