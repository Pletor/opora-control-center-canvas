"""Prostoje: uzel, který běží bez heartbeatu, nebo čeká po deadline. Čistá funkce nad řádkem `node_run`."""

from datetime import UTC, datetime, timedelta

HEARTBEAT_LIMIT = timedelta(minutes=5)


def stall_reason(node_run, now, heartbeat_limit=HEARTBEAT_LIMIT):
    """Vrátí důvod prostoje, nebo None. `node_run` je dict s poli tabulky `flow_node_runs`."""
    status = node_run.get("status")
    if status == "running":
        beat = node_run.get("last_heartbeat_at")
        if not beat:
            return "Uzel běží bez heartbeatu."
        silent = now - datetime.fromisoformat(beat)
        if silent > heartbeat_limit:
            return f"Uzel běží, heartbeat chybí {int(silent.total_seconds() // 60)} min."
    if status == "waiting":
        deadline = node_run.get("deadline")
        if deadline and datetime.fromisoformat(deadline) <= now:
            return f"Uzel čeká na {node_run.get('waiting_for') or '?'} a deadline vypršel {deadline}."
    return None


def list_stalls(db, now=None, heartbeat_limit=HEARTBEAT_LIMIT):
    """Otevřené uzly všech běhů, které stojí, s důvodem."""
    now = now or datetime.now(UTC)
    rows = db.execute(
        "SELECT n.*, r.workflow_version_id FROM flow_node_runs n JOIN flow_runs r ON r.id=n.run_id "
        "WHERE n.status IN ('running','waiting') ORDER BY n.rowid"
    ).fetchall()
    stalls = []
    for row in rows:
        reason = stall_reason(dict(row), now, heartbeat_limit)
        if reason:
            stalls.append({**dict(row), "reason": reason})
    return stalls
