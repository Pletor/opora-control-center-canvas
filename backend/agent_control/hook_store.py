"""Soukromé SQLite úložiště bindingů a bezpečně zkrácené evidence hooků."""

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path


class HookStore:
    def __init__(self, root):
        self.path = Path(root) / "agent-control" / "hooks.sqlite"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS hook_bindings (
              id TEXT PRIMARY KEY, data TEXT NOT NULL, token_hash TEXT NOT NULL,
              client_path TEXT NOT NULL, root TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS hook_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT, binding_id TEXT NOT NULL, at TEXT NOT NULL,
              event TEXT NOT NULL, tool_name TEXT NOT NULL, decision TEXT NOT NULL,
              reason TEXT NOT NULL, task_revision INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS hook_events_binding ON hook_events(binding_id,id DESC);
        """)
        self.db.commit()

    def close(self):
        self.db.close()

    def transaction(self):
        return self.db

    def insert(self, binding, token_hash, client_path, root):
        self.db.execute("INSERT INTO hook_bindings VALUES(?,?,?,?,?,?)", (
            binding["id"], json.dumps(binding, ensure_ascii=False), token_hash, str(client_path), str(root),
            datetime.now(UTC).isoformat(),
        ))

    def row(self, binding_id):
        if not isinstance(binding_id, str) or len(binding_id) > 80:
            raise ValueError("Neplatné bindingId.")
        row = self.db.execute("SELECT * FROM hook_bindings WHERE id=?", (binding_id,)).fetchone()
        if row is None:
            raise ValueError("Hook binding nebyl nalezen.")
        return {**dict(row), "data": json.loads(row["data"])}

    def update(self, binding):
        self.db.execute("UPDATE hook_bindings SET data=? WHERE id=?", (
            json.dumps(binding, ensure_ascii=False), binding["id"],
        ))

    def scoped(self, project, workspace, node_id):
        rows = self.db.execute("SELECT data FROM hook_bindings").fetchall()
        return [json.loads(row["data"]) for row in rows if (
            json.loads(row["data"])["project"], json.loads(row["data"])["workspace"], json.loads(row["data"])["nodeId"]
        ) == (project, workspace, node_id)]

    def for_project(self, project):
        """Jen čtení: všechny bindingy projektu (veřejná data bez tokenu), pro přehled stavu práce."""
        with self.lock:
            rows = self.db.execute("SELECT data FROM hook_bindings").fetchall()
        return [data for data in (json.loads(row["data"]) for row in rows) if data.get("project") == project]

    def active_at_root(self, root):
        return self.db.execute(
            "SELECT data FROM hook_bindings WHERE root=?", (str(root),)
        ).fetchall()

    def event(self, binding_id, event, tool_name, decision, reason, revision):
        self.db.execute("INSERT INTO hook_events(binding_id,at,event,tool_name,decision,reason,task_revision) VALUES(?,?,?,?,?,?,?)", (
            binding_id, datetime.now(UTC).isoformat(), event, tool_name[:120], decision, reason[:240], revision,
        ))

    def events(self, binding_id):
        rows = self.db.execute("SELECT * FROM hook_events WHERE binding_id=? ORDER BY id DESC LIMIT 51", (binding_id,)).fetchall()
        return {
            "events": [{"id": str(r["id"]), "at": r["at"], "event": r["event"], "toolName": r["tool_name"],
                        "decision": r["decision"], "reason": r["reason"], "taskRevision": r["task_revision"]}
                       for r in rows[:50]],
            "truncated": len(rows) > 50,
        }
