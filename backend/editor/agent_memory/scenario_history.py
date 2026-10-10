"""Latest gate runs are taken from immutable accepted output records."""

import json

from backend.editor.agent_packet.desktop_v3_packets import redact_deep


def scenario_history(canvas, project, workspace):
    with canvas.reading(project):
        graph = canvas.view(project, workspace)["graph"]
        nodes = {node["id"]: node for node in graph["nodes"] if node.get("scenario")}
        runs = {node_id: [] for node_id in nodes}
        rows = canvas.db_for(project).execute(
            "SELECT node_id,record FROM agent_result_records WHERE project_id=? AND workspace_id=?"
            " AND json_type(record,'$.output.scenarioRun')='object' ORDER BY sequence DESC", (project, workspace))
        for row in rows:
            if row["node_id"] in runs and len(runs[row["node_id"]]) < 2:
                record = json.loads(row["record"])
                runs[row["node_id"]].append({"resultId": record["id"], "agent": record["agent"], **record["output"]["scenarioRun"]})
        result = {}
        for node_id, history in runs.items():
            latest = history[0] if history else None
            previous = history[1] if len(history) > 1 else None
            current = bool(latest and latest["command"] == nodes[node_id]["scenario"]["command"])
            comparable = bool(current and previous and latest["command"] == previous["command"])
            result[node_id] = {"latest": latest, "previous": previous, "current": current, "comparable": comparable,
                               "deltaPassed": latest["passed"] - previous["passed"] if comparable else None,
                               "deltaFailed": latest["failed"] - previous["failed"] if comparable else None}
        return redact_deep({"nodes": result})
