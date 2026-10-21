"""Global fail-closed session reservations survive project transaction rollback."""
from backend.canvas.opora_change_validation import identifier, scope
from backend.canvas.opora_execution_observer_auth import PROVIDER
from backend.canvas.opora_execution_observer_validation import resource_id
from backend.canvas.opora_hub_store import canonical

TABLE = "opora_execution_observer_sessions"
MAX_RESERVATIONS = 65536
MAX_BYTES = 64 * 1024 * 1024


def reservation(project, workspace, intent_id, session_id):
    scope({"project": project, "workspace": workspace})
    identifier(intent_id)
    resource_id(session_id)
    return {"provider": PROVIDER, "sessionId": session_id, "project": project,
            "workspace": workspace, "intentId": intent_id}


def verify(db, project, workspace, intent_id, session_id):
    value = reservation(project, workspace, intent_id, session_id)
    row = db.execute(f"SELECT project_id,workspace_id,intent_id,content FROM {TABLE}"
                     " WHERE provider=? AND session_id=?", (PROVIDER, session_id)).fetchone()
    if row is None or tuple(row) != (project, workspace, intent_id, canonical(value)):
        raise ValueError("Global provider session reservation is missing or inconsistent.")


def reserve(db, project, workspace, intent_id, session_id):
    if not db.in_transaction:
        raise RuntimeError("Session reservation requires a caller transaction.")
    value = reservation(project, workspace, intent_id, session_id)
    row = db.execute(f"SELECT 1 FROM {TABLE} WHERE (provider=? AND session_id=?) OR intent_id=?",
                     (PROVIDER, session_id, intent_id)).fetchone()
    if row:
        verify(db, project, workspace, intent_id, session_id)
        return
    raw = canonical(value)
    count, used = db.execute(f"SELECT COUNT(*),COALESCE(SUM(length(CAST(content AS BLOB))),0) FROM {TABLE}").fetchone()
    if count >= MAX_RESERVATIONS or used + len(raw.encode()) > MAX_BYTES:
        raise ValueError("Global provider session reservation quota exceeded.")
    db.execute(f"INSERT INTO {TABLE} VALUES(?,?,?,?,?,?)",
               (PROVIDER, session_id, project, workspace, intent_id, raw))
