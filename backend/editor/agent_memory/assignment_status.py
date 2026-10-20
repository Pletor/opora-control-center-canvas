"""Compare the latest reported assignment with current saved specification."""

import json

from backend.editor.agent_packet.assignment_scope import same_assignment
from backend.editor.agent_packet.specification_context import capture_specification


def assignment_status(canvas, project, workspace):
    """Stav zadání karet proti poslednímu výstupu nebo předávce. Výsledek se cachuje podle tokenu
    dat projektu (karta P3): opakované čtení beze změny nic nepřepočítává; každý zápis token změní."""
    with canvas.reading(project):
        key = ("assignment-status", project, workspace)
        token = canvas.view_token(project, workspace)
        cached = canvas.read_cache.get(key, token)
        if cached is not None:
            return cached
        result = _assignment_status(canvas, project, workspace)
        return canvas.read_cache.put(key, token, result) if token is not None else result


def _assignment_status(canvas, project, workspace):
    with canvas.reading(project):
        view = canvas.view(project, workspace)
        existing = {node["id"] for node in view["graph"]["nodes"]}
        rows = canvas.db_for(project).execute(
            "SELECT node_id,record FROM agent_result_records WHERE sequence IN ("
            "SELECT MAX(sequence) FROM agent_result_records WHERE project_id=? AND workspace_id=? GROUP BY node_id)",
            (project, workspace),
        ).fetchall()
        candidates = {row["node_id"]: (json.loads(row["record"]), "result") for row in rows}
        handoffs = canvas.db_for(project).execute(
            "SELECT node_id,record FROM assignment_snapshots WHERE sequence IN ("
            "SELECT MAX(sequence) FROM assignment_snapshots WHERE project_id=? AND workspace_id=? GROUP BY node_id)",
            (project, workspace),
        ).fetchall()
        for row in handoffs:
            record = json.loads(row["record"])
            previous = candidates.get(row["node_id"])
            if previous is None or record["createdAt"] >= previous[0]["createdAt"]:
                candidates[row["node_id"]] = (record, "handoff")
        nodes = {}
        for node_id, (record, source) in candidates.items():
            if node_id not in existing:
                continue
            if record.get("binding") != "bound":
                nodes[node_id] = {"status": "unbound", "resultId": record["id"]}
                continue
            current = capture_specification(canvas, project, workspace, node_id)
            nodes[node_id] = {"status": "current" if same_assignment(record, current) else "changed",
                              "resultId": record["id"]}
            if source == "handoff":
                nodes[node_id]["source"] = source
        return {"nodes": nodes}
