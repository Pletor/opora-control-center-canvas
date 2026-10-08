"""Derived sector progress: only a human gate plus closed descendant cards verifies it.

Fail-closed (upgrade-opora #33): sektor bez `gateNodeId` je ověřený teprve tehdy, když jsou
uzavřené všechny jeho karty (nebo ho člověk sám uzavřel). Vazba `next` do sektoru zamyká
jeho karty i tehdy, když vede z karty (recept „Ověření sektoru“ → další sektor)."""


def sector_status(graph, state):
    by_id = {node["id"]: node for node in graph["nodes"]}
    result = {}
    for sector in graph["nodes"]:
        if sector["kind"] != "sector":
            continue
        members = []
        for node in graph["nodes"]:
            if node["kind"] != "node":
                continue
            cursor, seen = node["parentId"], set()
            while cursor and cursor not in seen:
                if cursor == sector["id"]:
                    members.append(node["id"])
                    break
                seen.add(cursor)
                cursor = by_id.get(cursor, {}).get("parentId")
        closed = sum(bool(state["nodes"].get(n, {}).get("done", {}).get("confirmed")) for n in members)
        gate_id = sector.get("gateNodeId")
        gate = state["nodes"].get(gate_id, {}).get("done", {})
        own = state["nodes"].get(sector["id"], {}).get("done", {})
        if gate_id:
            scenario = by_id.get(gate_id, {}).get("scenario")
            run = state["nodes"].get(gate_id, {}).get("scenarioRun", {})
            scenario_ready = not scenario or (run.get("command") == scenario["command"] and run.get("failed") == 0)
            verified = bool(gate.get("confirmed") and gate.get("by") == "human" and members and closed == len(members) and scenario_ready)
        else:
            verified = bool(members and closed == len(members)) or bool(own.get("confirmed") and own.get("by") == "human")
        result[sector["id"]] = {"gateNodeId": gate_id, "status": "verified" if verified else "running", "closed": closed, "total": len(members)}
    return result


def sector_blockers(graph, state, node_id, statuses=None):
    statuses = sector_status(graph, state) if statuses is None else statuses
    by_id = {node["id"]: node for node in graph["nodes"]}
    scope, cursor = set(), node_id
    while cursor and cursor not in scope:
        scope.add(cursor)
        cursor = by_id.get(cursor, {}).get("parentId")
    blockers = {}
    for edge in graph["edges"]:
        source = by_id.get(edge["source"], {})
        target = by_id.get(edge["target"], {})
        if edge.get("port", "next") != "next" or edge["target"] not in scope or target.get("kind") != "sector":
            continue
        if source.get("kind") == "sector":
            blocked = statuses.get(edge["source"], {}).get("status") != "verified"
        else:
            blocked = not state["nodes"].get(edge["source"], {}).get("done", {}).get("confirmed")
        if blocked:
            blockers[source["id"]] = {"id": source["id"], "name": source["name"]}
    return list(blockers.values())
