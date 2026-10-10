"""Záznam obnovy smazaného obsahu a jeho jednorázové použití (docs/hromadne-mazani.md, „Backend“).

Před smazáním uzlů nebo vazby se do `removal_restores` uloží vše, co mazání zahodí: graf před
smazáním, `state.nodes` / `state.edges` smazaných položek, vynulované větve `onMet` / `onUnmet`
přeživších karet a řádky prostoru agenta. `restore` z něj vrátí to, co v plátně chybí, a záznam
spotřebuje. Importy Desktop v3 jsou až ve funkcích: `canvas_service` staví `RemovalService`.
"""

import json
import re
from datetime import UTC, datetime

RESTORE_KEYS = {"project", "workspace", "recoveryId", "digest"}
WORKSPACE_COLUMNS = "project_id,workspace_id,node_id,revision,sections,by,saved_at"


def _now():
    return datetime.now(UTC).isoformat()


def pointing_branches(state, removed_nodes):
    """Větve přeživších karet, které mířily na smazaný uzel (blok id + původní větev)."""
    found = []
    for node_id, node in state["nodes"].items():
        if node_id in removed_nodes:
            continue
        for block in node.get("blocks", []):
            for via in ("onMet", "onUnmet"):
                branch = block["state"][via]
                if branch["kind"] == "node" and branch["targetId"] in removed_nodes:
                    found.append({"nodeId": node_id, "blockId": block["id"], "via": via, "branch": branch})
    return found


def capture(canvas, db, recovery_id, project, workspace, graph, node_ids, edge_ids):
    """Uloží záznam obnovy; volající drží `canvas.lock_for(project)` a otevřenou transakci `db`."""
    from backend.editor.agent_memory.desktop_v3_state import DesktopV3State

    state = DesktopV3State(canvas).current(project, workspace)["state"]
    removed = set(node_ids)
    rows = []
    if node_ids:
        marks = ",".join("?" * len(node_ids))
        rows = [
            list(row)
            for row in db.execute(
                f"SELECT {WORKSPACE_COLUMNS} FROM agent_workspace_revisions"
                f" WHERE project_id=? AND workspace_id=? AND node_id IN ({marks})",
                (project, workspace, *node_ids),
            ).fetchall()
        ]
    record = {
        "graph": graph,
        "nodeIds": sorted(removed),
        "edgeIds": sorted(edge_ids),
        "stateNodes": {key: state["nodes"][key] for key in sorted(removed) if key in state["nodes"]},
        "stateEdges": {key: state["edges"][key] for key in sorted(edge_ids) if key in state["edges"]},
        "rules": [r for r in state["rules"] if r["scope"] == "node" and r["target"] in removed],
        "decisions": [d for d in state["decisions"] if d["nodeId"] in removed],
        "branches": pointing_branches(state, removed),
        "workspaceRows": rows,
    }
    db.execute(
        "INSERT INTO removal_restores VALUES(?,?,?,?,?,NULL)",
        (recovery_id, project, workspace, json.dumps(record, ensure_ascii=False), _now()),
    )


def _insert_in_order(current, restored, before):
    """Vloží obnovené položky za nejbližšího předchůdce z původního pořadí; jinak na začátek."""
    result = list(current)
    order = [item["id"] for item in before]
    for item in restored:
        position = 0
        index = order.index(item["id"])
        present = [entry["id"] for entry in result]
        for previous in reversed(order[:index]):
            if previous in present:
                position = present.index(previous) + 1
                break
        result.insert(position, item)
    return result


def merged_graph(current, record):
    """Aktuální graf + smazané uzly, které chybí, + smazané vazby, jejichž konce existují."""
    before = record["graph"]
    removed_nodes, removed_edges = set(record["nodeIds"]), set(record["edgeIds"])
    current_nodes = {item["id"] for item in current["nodes"]}
    restored = [n for n in before["nodes"] if n["id"] in removed_nodes and n["id"] not in current_nodes]
    node_ids = current_nodes | {n["id"] for n in restored}
    # Rodič mezitím smazaný jinde by graf zneplatnil; karta se pak vrátí na nejvyšší úroveň.
    restored = [n if n["parentId"] in node_ids or n["parentId"] is None else {**n, "parentId": None}
                for n in restored]
    current_edges = {item["id"] for item in current["edges"]}
    edges = [
        e for e in before["edges"]
        if e["id"] in removed_edges and e["id"] not in current_edges
        and e["source"] in node_ids and e["target"] in node_ids
    ]
    graph = {
        "nodes": _insert_in_order(current["nodes"], restored, before["nodes"]),
        "edges": _insert_in_order(current["edges"], edges, before["edges"]),
    }
    return graph, {n["id"] for n in restored}


def _clean_branches(node, graph_ids):
    """Obnovená karta nesmí nést větev na uzel, který mezitím z grafu zmizel."""
    from backend.editor.agent_memory.block_access import _default_branch

    blocks = node.get("blocks")
    if not blocks:
        return node

    def clean(branch):
        return _default_branch() if branch["kind"] == "node" and branch["targetId"] not in graph_ids else branch

    return {
        **node,
        "blocks": [
            {**b, "state": {**b["state"], "onMet": clean(b["state"]["onMet"]), "onUnmet": clean(b["state"]["onUnmet"])}}
            for b in blocks
        ],
    }


def restored_state(state, record, graph):
    from backend.editor.agent_memory.desktop_v3_state import default_done

    graph_nodes = {item["id"] for item in graph["nodes"]}
    graph_edges = {item["id"] for item in graph["edges"]}
    nodes = dict(state["nodes"])
    for key, value in record["stateNodes"].items():
        if key in graph_nodes and key not in nodes:
            nodes[key] = _clean_branches(value, graph_nodes)
    for item in record["branches"]:
        node = nodes.get(item["nodeId"])
        if node is None or node.get("done", default_done())["confirmed"]:
            continue
        if item["branch"]["targetId"] not in graph_nodes:
            continue
        blocks = node.get("blocks", [])
        if not any(b["id"] == item["blockId"] and b["state"][item["via"]]["kind"] == "none" for b in blocks):
            continue
        nodes[item["nodeId"]] = {
            **node,
            "blocks": [
                {**b, "state": {**b["state"], item["via"]: item["branch"]}} if b["id"] == item["blockId"] else b
                for b in blocks
            ],
        }
    edges = dict(state["edges"])
    for key, value in record["stateEdges"].items():
        if key in graph_edges and key not in edges:
            edges[key] = value
    result = {**state, "nodes": nodes, "edges": edges}
    for collection, target in (("rules", "target"), ("decisions", "nodeId")):
        present = {item["id"] for item in state[collection]}
        result[collection] = [*state[collection], *[
            item for item in record.get(collection, [])
            if item["id"] not in present and item[target] in graph_nodes
        ]]
    return result


def restore(canvas, payload):
    from backend.editor.agent_memory.desktop_v3_state import DesktopV3State

    if not isinstance(payload, dict) or set(payload) != RESTORE_KEYS:
        raise ValueError("Obnovení očekává project, workspace, recoveryId a digest.")
    project, workspace, recovery_id = payload["project"], payload["workspace"], payload["recoveryId"]
    if not isinstance(recovery_id, str) or not re.fullmatch(r"[0-9a-f]{32}", recovery_id):
        raise ValueError("Neplatný záznam obnovy.")
    with canvas.graph_lock_for(project):
        current = canvas.view(project, workspace)
        if current["readOnly"]:
            raise ValueError("Main je pouze pro čtení. Přepněte do pracovního prostoru.")
        if payload["digest"] != current["digest"]:
            raise ValueError("Plátno se změnilo v jiném okně. Obnovte ho.")
        db = canvas.db_for(project)
        with canvas.lock_for(project):
            row = db.execute(
                "SELECT record,used_at FROM removal_restores WHERE id=? AND project_id=? AND workspace_id=?",
                (recovery_id, project, workspace),
            ).fetchone()
        if row is None:
            raise ValueError("Záznam obnovy neexistuje.")
        if row["used_at"] is not None:
            raise ValueError("Obnovení už bylo použito.")
        record = json.loads(row["record"])
        graph, restored_nodes = merged_graph(current["graph"], record)
        view = canvas.save_graph(project, workspace, graph, current["digest"], undo=True)
        with canvas.lock_for(project), db:
            db.execute("UPDATE removal_restores SET used_at=? WHERE id=?", (_now(), recovery_id))
            for values in record["workspaceRows"]:
                if values[2] in restored_nodes:
                    db.execute(
                        f"INSERT OR IGNORE INTO agent_workspace_revisions({WORKSPACE_COLUMNS}) VALUES(?,?,?,?,?,?,?)",
                        values,
                    )
        store = DesktopV3State(canvas)
        with canvas.lock_for(project):
            stored = store.current(project, workspace)
        new_state = restored_state(stored["state"], record, view["graph"])
        if new_state != stored["state"]:
            store.save({"project": project, "workspace": workspace,
                        "expectedRevision": stored["revision"], "state": new_state})
        return {"view": view}
