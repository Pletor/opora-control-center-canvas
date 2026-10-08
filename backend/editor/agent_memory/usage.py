"""Agent-reported increments; incomplete history never masquerades as a zero total."""
import json

FIELDS = ("tokens", "durationMs", "attempts")


def total(samples):
    return {**{key: sum(s[key] for s in samples) if samples and all(s.get(key) is not None for s in samples) else None
               for key in FIELDS}, "reports": len(samples)}


def usage_summary(canvas, project, workspace):
    with canvas.graph_lock, canvas.lock:
        graph = canvas.view(project, workspace)["graph"]
        by_id = {n["id"]: n for n in graph["nodes"]}
        samples = {key: [] for key in by_id}
        rows = canvas.db_for(project).execute(
            "SELECT node_id,record FROM agent_result_records WHERE project_id=? AND workspace_id=?",
            (project, workspace),
        ).fetchall()
        for row in rows:
            if row["node_id"] in samples:
                samples[row["node_id"]].append(json.loads(row["record"])["output"].get("usage", {}))
        sectors = {n["id"]: list(samples[n["id"]]) for n in graph["nodes"] if n["kind"] == "sector"}
        for node_id, values in samples.items():
            seen, cursor = {node_id}, by_id[node_id]["parentId"]
            while cursor in by_id and cursor not in seen:
                seen.add(cursor)
                if cursor in sectors:
                    sectors[cursor].extend(values)
                cursor = by_id[cursor]["parentId"]
        return {"nodes": {key: total(values) for key, values in samples.items()},
                "sectors": {key: total(values) for key, values in sectors.items()},
                "source": "agent-reported", "mode": "increments-per-accepted-output"}
