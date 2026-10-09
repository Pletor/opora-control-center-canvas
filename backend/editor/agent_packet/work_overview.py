"""One read-only lifecycle view over authoritative completion, leases and blockers."""

import json

from backend.editor.agent_memory.card_leases import CardLeases
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.agent_packet.frontier import frontier

STATUSES = ("waiting", "claimed", "waiting-human", "proposed", "done", "blocked")


def work_overview(canvas, project, workspace):
    with canvas.graph_lock, canvas.lock:
        graph = canvas.view(project, workspace)["graph"]
        state = DesktopV3State(canvas).read(project, workspace)["state"]
        leases = CardLeases(canvas).summary(project, workspace)["nodes"]
        activity = {row["node_id"]: dict(row) for row in canvas.db_for(project).execute(
            "SELECT * FROM card_work_activity WHERE project_id=? AND workspace_id=?", (project, workspace)).fetchall()}
        nodes = {node["id"]: node for node in graph["nodes"]}
        rows = {}
        parents = {node["parentId"] for node in graph["nodes"] if node["kind"] in ("node", "sector")}
        for parent in parents:
            groups = frontier(graph, state, parent or "", {}, leases)
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
