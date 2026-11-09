"""Derived sector progress: only a human gate plus closed descendant cards verifies it.

Fail-closed (upgrade-opora #33): sektor bez `gateNodeId` je ověřený teprve tehdy, když jsou
uzavřené všechny jeho karty (nebo ho člověk sám uzavřel). Vazba `next` do sektoru zamyká
jeho karty i tehdy, když vede z karty (recept „Ověření sektoru“ → další sektor).

Výkon (docs/navrhy/2026-10-14-vykon-platna.md, oprava 7): předky se počítají jednou pro celý graf
(`sector_ancestry`, paměť po uzlech, cykly v `parentId` se uzavřou), vazby do sektorů se seskupí
podle cíle (`SectorEdges`). Výsledek je stejný jako původní procházení všech dvojic.
"""

EMPTY = frozenset()


def sector_ancestry(graph, by_id=None):
    """Funkce `id -> frozenset` sektorů, které leží na řetězu `parentId` od `id` (včetně něj).

    Řetěz končí na prázdném rodiči, chybějícím uzlu nebo prvním opakování (cyklus), přesně jako
    ruční procházení s množinou `seen`. Výsledky se pamatují, takže celý graf stojí O(N).
    """
    by_id = {node["id"]: node for node in graph["nodes"]} if by_id is None else by_id
    sectors = {node["id"] for node in graph["nodes"] if node["kind"] == "sector"}
    memo = {}

    def reach(start):
        if not start:
            return EMPTY
        path, position, cursor = [], {}, start
        while cursor and cursor not in memo and cursor not in position:
            position[cursor] = len(path)
            path.append(cursor)
            cursor = by_id.get(cursor, {}).get("parentId")
        if cursor and cursor in position:
            cycle = path[position[cursor]:]
            base = frozenset(item for item in cycle if item in sectors)
            for item in cycle:
                memo[item] = base
            path = path[:position[cursor]]
        else:
            base = memo[cursor] if cursor else EMPTY
        for item in reversed(path):
            if item in sectors:
                base = base | {item}
            memo[item] = base
        return memo[start]

    return reach


def sector_status(graph, state, by_id=None):
    by_id = {node["id"]: node for node in graph["nodes"]} if by_id is None else by_id
    sectors = [node for node in graph["nodes"] if node["kind"] == "sector"]
    total, closed = {}, {}
    if sectors:
        reach = sector_ancestry(graph, by_id)
        for node in graph["nodes"]:
            if node["kind"] != "node":
                continue
            confirmed = bool(state["nodes"].get(node["id"], {}).get("done", {}).get("confirmed"))
            for sector_id in reach(node["parentId"]):
                total[sector_id] = total.get(sector_id, 0) + 1
                closed[sector_id] = closed.get(sector_id, 0) + confirmed
    result = {}
    for sector in sectors:
        count, done = total.get(sector["id"], 0), closed.get(sector["id"], 0)
        gate_id = sector.get("gateNodeId")
        gate = state["nodes"].get(gate_id, {}).get("done", {})
        own = state["nodes"].get(sector["id"], {}).get("done", {})
        if gate_id:
            scenario = by_id.get(gate_id, {}).get("scenario")
            run = state["nodes"].get(gate_id, {}).get("scenarioRun", {})
            scenario_ready = not scenario or (run.get("command") == scenario["command"] and run.get("failed") == 0)
            verified = bool(gate.get("confirmed") and gate.get("by") in ("human", "agent") and count and done == count and scenario_ready)
        else:
            verified = bool(count and done == count) or bool(own.get("confirmed") and own.get("by") in ("human", "agent"))
        result[sector["id"]] = {"gateNodeId": gate_id, "status": "verified" if verified else "running", "closed": done, "total": count}
    return result


class SectorEdges:
    """Vazby `next` do sektorů seskupené podle cíle; postaví se jednou pro mnoho dotazů `sector_blockers`."""

    def __init__(self, graph, by_id=None):
        self.by_id = {node["id"]: node for node in graph["nodes"]} if by_id is None else by_id
        self.into = {}
        for position, edge in enumerate(graph["edges"]):
            source, target = self.by_id.get(edge["source"], {}), self.by_id.get(edge["target"], {})
            if "relation" in edge or edge.get("port", "next") != "next" or target.get("kind") != "sector":
                continue
            self.into.setdefault(edge["target"], []).append((position, edge["source"], source))

    def scope(self, node_id):
        scope, cursor = set(), node_id
        while cursor and cursor not in scope:
            scope.add(cursor)
            cursor = self.by_id.get(cursor, {}).get("parentId")
        return scope


def sector_blockers(graph, state, node_id, statuses=None, edges=None):
    """Kdo zamyká kartu vazbou `next` do jejího sektoru (nebo předka). `edges` = předpočítané `SectorEdges`."""
    edges = SectorEdges(graph) if edges is None else edges
    statuses = sector_status(graph, state, edges.by_id) if statuses is None else statuses
    hits = sorted(hit for target in edges.scope(node_id) for hit in edges.into.get(target, ()))
    blockers = {}
    for _, source_id, source in hits:
        if source.get("kind") == "sector":
            blocked = statuses.get(source_id, {}).get("status") != "verified"
        else:
            blocked = not state["nodes"].get(source_id, {}).get("done", {}).get("confirmed")
        if blocked:
            blockers[source["id"]] = {"id": source["id"], "name": source["name"]}
    return list(blockers.values())
