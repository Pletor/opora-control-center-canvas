"""Runtime conditions for closing a card under a human sector grant."""

from datetime import datetime

from backend.editor.agent_memory.desktop_v3_state import autonomy_active


def sector_of(graph, node_id):
    by_id = {node["id"]: node for node in graph["nodes"]}
    current = by_id.get(node_id, {}).get("parentId")
    seen = set()
    while current and current not in seen:
        seen.add(current)
        node = by_id.get(current, {})
        if node.get("kind") == "sector":
            return current
        current = node.get("parentId")
    return None


def authorize_close(graph, state, node_id, stamp, previous=None):
    """`previous` = uložený stav před tímto výstupem: bloky musí být `met` už tam (upgrade-opora #32)."""
    node = next(node for node in graph["nodes"] if node["id"] == node_id)
    sector = sector_of(graph, node_id)
    if not sector or not autonomy_active(state, sector, datetime.fromisoformat(stamp)):
        raise ValueError("Karta nemá platný lidský souhlas s autonomií svého sektoru.")
    # Existing boundary cards and named verification cards remain human-controlled.
    gate = any(n.get("gateNodeId") == node_id for n in graph["nodes"])
    gate = gate or node["name"].strip().casefold().startswith("[gate]") or "ověření sektoru" in node["name"].casefold()
    gate = gate or any(edge["source"] == node_id and edge.get("port", "next") == "next"
                       and sector_of(graph, edge["target"]) != sector for edge in graph["edges"])
    if node["kind"] != "node" or gate:
        raise ValueError("Sektor a jeho ověřovací bránu potvrzuje vždy člověk.")
    blocks = state["nodes"].get(node_id, {}).get("blocks", [])
    if not blocks or any(block["state"]["status"] != "met" for block in blocks):
        raise ValueError("Autonomní uzavření vyžaduje alespoň jeden blok a všechny bloky met.")
    earlier = (state if previous is None else previous)["nodes"].get(node_id, {}).get("blocks", [])
    if not earlier or any(block["state"]["status"] != "met" for block in earlier):
        raise ValueError("Autonomní uzavření vyžaduje bloky splněné už v předchozím výstupu; "
                         "nejdřív je nahlaste jako met, uzavřete až dalším výstupem.")
    if not node.get("checks"):
        raise ValueError("Autonomní uzavření vyžaduje předepsané kontroly karty; bez nich kartu potvrzuje člověk.")
    evidence = state["nodes"].get(node_id, {}).get("evidence")
    if evidence is None or any(evidence[key]["status"] != "passed" for key in ("tests", "review", "merge")):
        raise ValueError("Autonomní uzavření vyžaduje tests, review i merge passed; N/A nebo chybějící důkaz potvrzuje člověk.")
    return sector
