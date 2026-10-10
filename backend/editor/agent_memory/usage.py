"""Agent-reported increments; incomplete history never masquerades as a zero total."""
import json

FIELDS = ("tokens", "durationMs", "attempts")


def total(samples):
    return {**{key: sum(s[key] for s in samples) if samples and all(s.get(key) is not None for s in samples) else None
               for key in FIELDS}, "reports": len(samples)}


def usage_summary(canvas, project, workspace):
    """Součty spotřeby po kartách a sektorech. Cache podle tokenu dat projektu (karta P3): každý nový
    výstup agenta token změní; výsledek je sdílený, jen ke čtení."""
    with canvas.reading(project):
        key = ("usage-summary", project, workspace)
        token = canvas.view_token(project, workspace)
        cached = canvas.read_cache.get(key, token)
        if cached is not None:
            return cached
        result = _usage_summary(canvas, project, workspace)
        return canvas.read_cache.put(key, token, result) if token is not None else result


def _usage_summary(canvas, project, workspace):
    with canvas.reading(project):
        graph = canvas.view(project, workspace)["graph"]
        by_id = {n["id"]: n for n in graph["nodes"]}
        samples = {key: [] for key in by_id}
        # Z celého záznamu výstupu stačí `output.usage`; vybere ho SQLite, Python neparsuje celé záznamy.
        rows = canvas.db_for(project).execute(
            "SELECT node_id,json_extract(record,'$.output.usage') AS usage FROM agent_result_records"
            " WHERE project_id=? AND workspace_id=?",
            (project, workspace),
        ).fetchall()
        for row in rows:
            if row["node_id"] in samples:
                samples[row["node_id"]].append(json.loads(row["usage"]) if row["usage"] is not None else {})
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
