"""Transactional invalidations; readers retain a scoped cursor across reconnects."""
import json
from datetime import UTC, datetime

from backend.editor.research import model


def record(db, project, workspace, key, result, actor, agent=None):
    """Call inside the revision transaction, never commit independently."""
    payload = {"type": "research.changed", "at": datetime.now(UTC).isoformat(),
               "actor": actor, "agent": agent,
               "cards": [{"id": c["id"], "revision": c["revision"]} for c in result["cards"]],
               "edges": [{"id": e["id"], "revision": e["revision"]} for e in result["edges"]]}
    db.execute("INSERT INTO research_events(project_id,workspace_id,batch_key,payload) VALUES (?,?,?,?)",
               (project, workspace, key, json.dumps(payload, ensure_ascii=False)))


def listing(service, project, workspace, after=0, limit=100):
    from backend.editor.research import question_journal, service as research
    research._scope(service, project, workspace)
    if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 500:
        model.fail("Event cursor must be nonnegative and limit between 1 and 500.")
    # Conversation source events must be projected before checking for changes.
    question_journal.reconcile(service, project, workspace)
    with service.reading(project):
        rows = service.db_for(project).execute(
            "SELECT cursor,payload FROM research_events WHERE project_id=? AND workspace_id=? "
            "AND cursor>? ORDER BY cursor LIMIT ?", (project, workspace, after, limit + 1)).fetchall()
    selected = rows[:limit]
    return {"project": project, "workspace": workspace,
            "events": [{**json.loads(row[1]), "cursor": row[0]} for row in selected],
            "nextCursor": selected[-1][0] if selected else after, "hasMore": len(rows) > limit}
