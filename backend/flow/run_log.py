"""Append-only log toků je zdroj pravdy; `flow_runs` a `flow_node_runs` jsou jeho projekce.

Každá změna stavu jde přes `append`: zapíše událost a v téže transakci ji promítne do tabulek běhu.
Volající drží transakci (`with db:`), aby událost a projekce vznikly spolu, nebo vůbec.
"""

import json
from datetime import UTC, datetime


def now_iso(moment=None):
    return (moment or datetime.now(UTC)).isoformat()


def _dump(value):
    return json.dumps(value, ensure_ascii=False, default=str)


def _project(db, run_id, node_run_id, kind, p, ts):
    if kind == "run.created":
        db.execute(
            "INSERT INTO flow_runs(id,workflow_version_id,trigger,status,parent_run_id,created_at,updated_at) "
            "VALUES(?,?,?,'queued',?,?,?)",
            (run_id, p["workflow_version_id"], _dump(p["trigger"]), p.get("parent_run_id"), ts, ts),
        )
    elif kind == "run.status":
        db.execute("UPDATE flow_runs SET status=?, updated_at=? WHERE id=?", (p["status"], ts, run_id))
    elif kind == "node.queued":
        db.execute(
            "INSERT INTO flow_node_runs(id,run_id,node_id,attempt,status,idempotency_key,input_ref) "
            "VALUES(?,?,?,?,'queued',?,?)",
            (node_run_id, run_id, p["node_id"], p["attempt"], p["idempotency_key"], _dump(p["input"])),
        )
    elif kind == "node.started":
        db.execute("UPDATE flow_node_runs SET status='running', started_at=?, last_heartbeat_at=? WHERE id=?",
                   (ts, ts, node_run_id))
    elif kind == "node.heartbeat":
        db.execute("UPDATE flow_node_runs SET last_heartbeat_at=? WHERE id=? AND status='running'", (ts, node_run_id))
    elif kind == "node.waiting":
        db.execute(
            "UPDATE flow_node_runs SET status='waiting', waiting_for=?, deadline=?, last_heartbeat_at=? WHERE id=?",
            (p["waiting_for"], p["deadline"], ts, node_run_id),
        )
    elif kind == "node.succeeded":
        db.execute(
            "UPDATE flow_node_runs SET status='succeeded', output_port=?, output_ref=?, ended_at=?, "
            "last_heartbeat_at=?, provider=?, model=?, cost_usd=? WHERE id=?",
            (p["port"], _dump(p.get("output")), ts, ts, p.get("provider"), p.get("model"), p.get("cost_usd"),
             node_run_id),
        )
    elif kind == "node.failed":
        db.execute("UPDATE flow_node_runs SET status='failed', error=?, ended_at=? WHERE id=?",
                   (p["error"], ts, node_run_id))
    # Ostatní typy (např. chyby z pláten 2–4) jsou jen v logu, projekci nemění.


def append(db, run_id, node_run_id, kind, payload, canvas=1, moment=None):
    ts = now_iso(moment)
    cursor = db.execute(
        "INSERT INTO flow_log_events(run_id,node_run_id,ts,type,payload,canvas) VALUES(?,?,?,?,?,?)",
        (run_id, node_run_id, ts, kind, _dump(payload), canvas),
    )
    _project(db, run_id, node_run_id, kind, payload, ts)
    return cursor.lastrowid


def read_log(db, run_id, after_seq=0, limit=500):
    rows = db.execute(
        "SELECT * FROM flow_log_events WHERE run_id=? AND seq>? ORDER BY seq LIMIT ?", (run_id, after_seq, limit)
    ).fetchall()
    return [{**dict(row), "payload": json.loads(row["payload"])} for row in rows]
