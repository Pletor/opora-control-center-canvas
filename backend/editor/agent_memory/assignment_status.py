"""Compare the latest reported assignment with current saved specification."""

import json

from backend.editor.agent_packet.specification_context import capture_specification


def assignment_status(canvas, project, workspace):
    with canvas.graph_lock, canvas.lock:
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
            nodes[node_id] = {"status": "current" if current["contextVersion"] == record["contextVersion"] else "changed",
                              "resultId": record["id"]}
            if source == "handoff":
                nodes[node_id]["source"] = source
        return {"nodes": nodes}
