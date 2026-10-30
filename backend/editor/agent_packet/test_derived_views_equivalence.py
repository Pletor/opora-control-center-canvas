"""Oprava 7 výkonu plátna: indexované `sector_status`, `sector_blockers`, `frontier` a přehled práce
dávají přesně stejný výstup jako původní procházení všech dvojic (referenční kopie níže, z 9a0ceae).

Syntetické grafy pokrývají vnořené sektory, cykly v `parentId`, chybějící rodiče, uzavřené karty,
brány se scénářem, vazby ze sektorů i karet a prázdný graf.
"""

import copy
import json
import random

import pytest

from backend.editor.agent_memory.card_pipeline import summary as pipeline_summary
from backend.editor.agent_packet.desktop_v3_packets import redact_deep
from backend.editor.agent_packet.frontier import FrontierIndex, claim_of, frontier, ticket_type
from backend.editor.agent_packet.sector_status import sector_blockers, sector_status
from backend.editor.agent_packet.work_overview import STATUSES, overview_of


# --- Referenční (původní) implementace -------------------------------------------------------------

# Od plné autonomie (#137) uzavře sektor i `agent`; kdo smí zapsat, hlídá služba (acts_as_human), odvozený pohled čte zapsané `by`.
def old_sector_status(graph, state):
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
            verified = bool(gate.get("confirmed") and gate.get("by") in ("human", "agent") and members and closed == len(members) and scenario_ready)
        else:
            verified = bool(members and closed == len(members)) or bool(own.get("confirmed") and own.get("by") in ("human", "agent"))
        result[sector["id"]] = {"gateNodeId": gate_id, "status": "verified" if verified else "running", "closed": closed, "total": len(members)}
    return result


def old_sector_blockers(graph, state, node_id, statuses=None):
    statuses = old_sector_status(graph, state) if statuses is None else statuses
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


def old_frontier(graph, state, sector_id, frames, leases=None):
    """Mapa wayfinderu nad sektorem: karty sektoru rozdělené na uzavřené, převzaté, blokované a frontier.

    Blokace je vazba `next` (nebo bez portu) z neuzavřené karty. Převzetí je řádek `Převzato:`
    v `agent-workspace.frame`. Pořadí karet je pořadí v grafu.
    """
    nodes = graph.get('nodes', [])
    sector = next((n for n in nodes if n.get('id') == sector_id), None) if sector_id else {'id': '', 'name': 'Canvas', 'kind': 'sector'}
    if sector is None or sector.get('kind') not in ('sector', 'node'):
        raise ValueError('--node musí být ID sektoru (mapy) v tomto workspace.')
    names = {n['id']: n.get('name', '') for n in nodes}
    cards = [n for n in nodes if n.get('parentId') == (sector_id or None) and n.get('kind') in ('node', 'sector')]
    done = {cid: bool(state.get('nodes', {}).get(cid, {}).get('done', {}).get('confirmed')) for cid in names}
    statuses = old_sector_status(graph, state)
    for sid, status in statuses.items():
        done[sid] = status['status'] == 'verified'
    out = {'map': {'id': sector_id, 'name': sector.get('name', '')}, 'frontier': [], 'claimed': [], 'blocked': [], 'waiting': [], 'closed': [],
           'needsRouting': []}
    for card in cards:
        cid = card['id']
        row = {'id': cid, 'name': card.get('name', ''), 'type': ticket_type(card.get('name'))}
        # Pipeline karty: relace = karta + etapa `current`; karta bez pipeline čeká na router.
        stages = state.get('nodes', {}).get(cid, {}).get('stages')
        if card.get('kind') == 'node':
            row['pipeline'] = pipeline_summary(stages)
        blockers = [e['source'] for e in graph.get('edges', [])
                    if e.get('target') == cid and e.get('port', 'next') == 'next' and not done.get(e.get('source'), False)]
        blockers = list(dict.fromkeys([*blockers, *(b['id'] for b in old_sector_blockers(graph, state, cid, statuses))]))
        claim = claim_of(frames.get(cid, ''))
        if leases is not None:
            lease = leases.get(cid)
            claim = lease['owner'] if lease and lease['active'] else ''
            if lease:
                row['lease'] = lease
        waiting = [{'blockId': b['id'], 'ask': b['state'].get('note') or b['state'].get('condition') or b.get('title', '')}
                   for b in state.get('nodes', {}).get(cid, {}).get('blocks', [])
                   if b.get('state', {}).get('status') == 'blocked']
        waiting += [{'stageId': s['id'], 'ask': f"Pipeline: etapa „{s['title']}“ selhala i po opakováních. {s['note']}".strip()}
                    for s in row.get('pipeline', {}).get('stuck', [])]
        if not done[cid] and card.get('kind') == 'node' and not row['pipeline']['routed']:
            out['needsRouting'].append({'id': cid, 'name': row['name'], 'type': row['type']})
        if done[cid]:
            out['closed'].append(row)
        elif waiting:
            out['waiting'].append({**row, 'waitingOnHuman': waiting, 'claim': claim,
                                   'blockedBy': [{'id': b, 'name': names.get(b, '')} for b in blockers]})
        elif claim:
            out['claimed'].append({**row, 'claim': claim})
        elif blockers:
            out['blocked'].append({**row, 'blockedBy': [{'id': b, 'name': names.get(b, '')} for b in blockers]})
        else:
            out['frontier'].append(row)
    ids = {sector_id, *(c['id'] for c in cards)}
    out['decisions'] = [{k: d[k] for k in ('id', 'text', 'nodeId', 'pinned', 'by', 'createdAt') if k in d} for d in state.get('decisions', []) if d.get('nodeId') in ids]
    out['fog'] = [{'id': n['id'], 'name': n.get('name', '')} for n in nodes if n.get('parentId') == (sector_id or None) and n.get('kind') == 'comment']
    return redact_deep(out)


def old_overview(graph, state, leases, activity):
    nodes = {node["id"]: node for node in graph["nodes"]}
    rows = {}
    parents = {node["parentId"] for node in graph["nodes"] if node["kind"] in ("node", "sector")}
    for parent in parents:
        groups = old_frontier(graph, state, parent or "", {}, leases)
        for group, status in (("frontier", "waiting"), ("claimed", "claimed"), ("waiting", "waiting-human"), ("blocked", "blocked"), ("closed", "done")):
            for item in groups[group]:
                node_id = item["id"]
                done = state["nodes"].get(node_id, {}).get("done", {})
                current = activity.get(node_id, {})
                status_value = status
                if status not in ("done", "waiting-human") and done.get("by") == "agent" and not done.get("confirmed"):
                    status_value = "proposed"
                rows[node_id] = {"id": node_id, "name": item["name"], "status": status_value,
                    "agent": item.get("claim") or current.get("agent", ""),
                    "startedAt": current.get("started_at"), "lastActivity": max(filter(None, [current.get("updated_at"), done.get("at")]), default=None),
                    "touched": json.loads(current["touched"]) if current.get("touched") is not None else None,
                    "waitingOnHuman": item.get("waitingOnHuman", []), "blockedBy": item.get("blockedBy", [])}
    sectors = {}
    for sector in graph["nodes"]:
        if sector["kind"] != "sector":
            continue
        counts = dict.fromkeys(STATUSES, 0)
        for node_id, row in rows.items():
            if nodes[node_id]["kind"] != "node":
                continue
            cursor, seen = nodes[node_id]["parentId"], set()
            while cursor and cursor not in seen:
                if cursor == sector["id"]:
                    counts[row["status"]] += 1
                    break
                seen.add(cursor)
                cursor = nodes.get(cursor, {}).get("parentId")
        sectors[sector["id"]] = counts
    return {"nodes": rows, "sectors": sectors}


# --- Syntetické grafy ------------------------------------------------------------------------------

def synthetic(seed, size=60):
    rnd = random.Random(seed)
    nodes = []
    for i in range(size):
        kind = rnd.choice(["sector", "sector", "node", "node", "node", "node", "comment"])
        nodes.append({"id": f"x{i}", "kind": kind, "name": f"[task] K{i}" if i % 3 else f"K{i} sk-{'a' * 24}", "parentId": None})
    ids = [n["id"] for n in nodes]
    for node in nodes:
        roll = rnd.random()
        if roll < 0.25:
            node["parentId"] = None
        elif roll < 0.3:
            node["parentId"] = "missing-" + node["id"]
        elif roll < 0.35:
            node["parentId"] = node["id"]  # smyčka sama na sebe
        else:
            node["parentId"] = rnd.choice(ids)  # může uzavřít cyklus
    sectors = [n for n in nodes if n["kind"] == "sector"]
    for sector in sectors:
        if rnd.random() < 0.4:
            sector["gateNodeId"] = rnd.choice(ids)
    if sectors:
        gate = next((n for n in nodes if n["id"] == sectors[0].get("gateNodeId")), None)
        if gate:
            gate["scenario"] = {"command": "pytest"}
    edges = []
    for i in range(size * 2):
        port = rnd.choice(["next", "next", "block", None])
        edge = {"id": f"e{i}", "source": rnd.choice(ids), "target": rnd.choice(ids)}
        if port:
            edge["port"] = port
        edges.append(edge)
    state_nodes = {}
    for node_id in ids:
        roll = rnd.random()
        entry = {}
        if roll < 0.3:
            entry["done"] = {"confirmed": True, "by": rnd.choice(["human", "agent", "autonomy"]), "at": "2026-10-14T10:00:00"}
        elif roll < 0.4:
            entry["done"] = {"confirmed": False, "by": "agent", "at": "2026-10-14T11:00:00"}
        if rnd.random() < 0.15:
            entry["blocks"] = [{"id": "b1", "title": "B", "state": {"status": "blocked", "note": "", "condition": "Čeká"}}]
        if rnd.random() < 0.1:
            entry["scenarioRun"] = {"command": "pytest", "failed": rnd.choice([0, 1])}
        if entry:
            state_nodes[node_id] = entry
    state = {"nodes": state_nodes, "decisions": [{"id": f"d{i}", "text": "D", "nodeId": rnd.choice(ids + [""])} for i in range(5)]}
    leases = {node_id: {"owner": "agent", "active": rnd.random() < 0.5} for node_id in rnd.sample(ids, k=min(5, len(ids)))}
    return {"nodes": nodes, "edges": edges}, state, leases


GRAPHS = [synthetic(seed) for seed in range(40)] + [synthetic(seed, size=6) for seed in range(40, 60)]
GRAPHS.append(({"nodes": [], "edges": []}, {"nodes": {}}, {}))


@pytest.mark.parametrize("graph,state,leases", GRAPHS)
def test_sector_status_and_blockers_match_reference(graph, state, leases):
    statuses = sector_status(graph, state)
    assert statuses == old_sector_status(graph, state)
    assert json.dumps(statuses) == json.dumps(old_sector_status(graph, state))
    for node in graph["nodes"]:
        assert sector_blockers(graph, state, node["id"]) == old_sector_blockers(graph, state, node["id"])
        assert sector_blockers(graph, state, node["id"], statuses) == old_sector_blockers(graph, state, node["id"], statuses)


def outcome(call):
    """JSON výsledku, nebo typ výjimky: stará i nová cesta musí selhat stejně (např. rodič mimo graf)."""
    try:
        return json.dumps(call(), ensure_ascii=False)
    except (ValueError, KeyError) as error:
        return type(error).__name__


def without_missing_parents(graph):
    """Rodič mimo graf nebo komentář shodí přehled (stejně dřív i teď); tady se přepojí na kořen."""
    graph = copy.deepcopy(graph)
    ids = {n["id"] for n in graph["nodes"] if n["kind"] != "comment"}
    for node in graph["nodes"]:
        if node["parentId"] and node["parentId"] not in ids:
            node["parentId"] = None
    return graph


ACTIVITY = {f"x{i}": {"agent": "worker", "started_at": "2026-10-14T09:00:00", "updated_at": "2026-10-14T12:00:00",
                      "touched": json.dumps(["src/a.py"]) if i % 2 else None} for i in range(0, 60, 4)}


@pytest.mark.parametrize("graph,state,leases", GRAPHS)
def test_frontier_matches_reference_for_every_parent_with_and_without_shared_index(graph, state, leases):
    index = FrontierIndex(graph, state)
    frames = {n["id"]: "Převzato: agent-x" for n in graph["nodes"][::5]}
    for parent in sorted({"", "nope", *(str(n["parentId"]) for n in graph["nodes"] if n["parentId"]), *(n["id"] for n in graph["nodes"])}):
        expected = outcome(lambda: old_frontier(graph, state, parent, frames, leases))
        assert outcome(lambda: frontier(graph, state, parent, frames, leases)) == expected
        assert outcome(lambda: frontier(graph, state, parent, frames, leases, index)) == expected
        assert outcome(lambda: frontier(graph, state, parent, frames)) == outcome(lambda: old_frontier(graph, state, parent, frames))


@pytest.mark.parametrize("graph,state,leases", GRAPHS)
def test_overview_matches_reference(graph, state, leases):
    assert outcome(lambda: overview_of(graph, state, leases, ACTIVITY)) == outcome(lambda: old_overview(graph, state, leases, ACTIVITY))
    clean = without_missing_parents(graph)
    expected = outcome(lambda: old_overview(clean, state, leases, ACTIVITY))
    assert expected.startswith("{")
    assert outcome(lambda: overview_of(clean, state, leases, ACTIVITY)) == expected


def test_frontier_matches_recorded_reference_on_cycle_and_missing_parent():
    graph = {"nodes": [{"id": "s", "kind": "sector", "name": "S", "parentId": "t"}, {"id": "t", "kind": "sector", "name": "T", "parentId": "s"},
                       {"id": "a", "kind": "node", "name": "A", "parentId": "s"}, {"id": "b", "kind": "node", "name": "B", "parentId": "gone"},
                       {"id": "c", "kind": "node", "name": "C", "parentId": "s"}],
             "edges": [{"id": "e1", "source": "b", "target": "t"}, {"id": "e2", "source": "a", "target": "c", "port": "next"}]}
    state = {"nodes": {"a": {"done": {"confirmed": True}}}}
    assert sector_status(graph, state) == old_sector_status(graph, state) == {
        "s": {"gateNodeId": None, "status": "running", "closed": 1, "total": 2},
        "t": {"gateNodeId": None, "status": "running", "closed": 1, "total": 2}}
    result = frontier(graph, state, "s", {})
    assert [r["id"] for r in result["closed"]] == ["a"]
    assert result["blocked"][0]["blockedBy"] == [{"id": "b", "name": "B"}]
