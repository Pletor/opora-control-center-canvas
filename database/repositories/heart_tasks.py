"""Řádky `heart_tasks` (docs/brain-gate.md §6, H1b): fronta úkolů, které píše člověk (později srdce) a bere pracovník.

Stavy: `ready` → `assigned` (drží ho jedna relace) → `done` | `failed`, nebo `ready` znovu po červeném hlášení;
`cancelled` kdykoli před koncem. `body` a `report` jsou text JSON. Transakci vlastní volající.
Pořadí (docs/brain-heart.md §5): nižší `task_order` jde dřív, při shodě rozhoduje `seq`."""
import json
import sqlite3

COLUMNS = ("seq", "id", "project_id", "workspace_id", "node_id", "title", "body", "status", "session_id", "attempts",
           "created_by", "report", "created_at", "updated_at", "task_order")
OPEN = ("ready", "assigned")
SELECT = "SELECT " + ",".join(COLUMNS) + " FROM heart_tasks"


def public(row):
    """Úkol v podobě, jakou vrací API."""
    if row is None:
        return None
    value = dict(zip(COLUMNS, tuple(row)))
    return {"taskId": value["id"], "seq": value["seq"], "workspaceId": value["workspace_id"], "nodeId": value["node_id"],
            "title": value["title"], "body": json.loads(value["body"]), "status": value["status"],
            "sessionId": value["session_id"], "attempts": value["attempts"], "createdBy": value["created_by"],
            "report": None if value["report"] is None else json.loads(value["report"]),
            "createdAt": value["created_at"], "updatedAt": value["updated_at"], "order": value["task_order"]}


def ensure_order_column(db):
    """Doplní `task_order` do tabulky z H1b (aditivně, idempotentně i při souběžném otevření)."""
    def columns():
        return {row[1] for row in db.execute("PRAGMA table_info(heart_tasks)")}
    if not columns() or "task_order" in columns():
        return
    try:
        db.execute("ALTER TABLE heart_tasks ADD COLUMN task_order INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        if "task_order" not in columns():
            raise


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class HeartTaskStore:
    def __init__(self, db, project):
        self.db, self.project = db, project

    def insert(self, task_id, workspace, node_id, title, body, created_by, at, order=0):
        """Uloží úkol ve stavu `ready`; vrací jeho `seq`."""
        cursor = self.db.execute(
            "INSERT INTO heart_tasks(id,project_id,workspace_id,node_id,title,body,status,created_by,created_at,"
            "updated_at,task_order) VALUES(?,?,?,?,?,?,'ready',?,?,?,?)",
            (task_id, self.project, workspace, node_id, title, _json(body), created_by, at, at, order))
        return cursor.lastrowid

    def get(self, task_id):
        return public(self.db.execute(SELECT + " WHERE project_id=? AND id=?", (self.project, task_id)).fetchone())

    def list(self, workspace, status=None, limit=200):
        """Úkoly pracovního prostoru od nejstaršího, volitelně jen v jednom stavu."""
        query, args = SELECT + " WHERE project_id=? AND workspace_id=?", [self.project, workspace]
        if status:
            query, args = query + " AND status=?", [*args, status]
        rows = self.db.execute(query + " ORDER BY seq LIMIT ?", (*args, limit)).fetchall()
        return [public(row) for row in rows]

    def held_by(self, session_id):
        """Úkol, který relace právě drží (`assigned`), nebo None."""
        return public(self.db.execute(SELECT + " WHERE project_id=? AND session_id=? AND status='assigned'"
                                      " ORDER BY seq LIMIT 1", (self.project, session_id)).fetchone())

    def oldest_ready(self, workspace):
        return public(self.db.execute(SELECT + " WHERE project_id=? AND workspace_id=? AND status='ready'"
                                      " ORDER BY task_order, seq LIMIT 1", (self.project, workspace)).fetchone())

    def assign(self, task_id, session_id, at):
        """Přidělí připravený úkol relaci; True, když ho přidělilo právě toto volání."""
        cursor = self.db.execute(
            "UPDATE heart_tasks SET status='assigned', session_id=?, updated_at=? WHERE project_id=? AND id=?"
            " AND status='ready'", (session_id, at, self.project, task_id))
        return cursor.rowcount == 1

    def finish(self, task_id, session_id, status, attempts, report, at):
        """Zapíše výsledek hlášení úkolu drženého relací: `done`, `failed`, nebo zpět `ready` (bez relace)."""
        holder = session_id if status != "ready" else None
        cursor = self.db.execute(
            "UPDATE heart_tasks SET status=?, session_id=?, attempts=?, report=?, updated_at=? WHERE project_id=?"
            " AND id=? AND status='assigned' AND session_id=?",
            (status, holder, attempts, _json(report), at, self.project, task_id, session_id))
        return cursor.rowcount == 1

    def cancel(self, task_id, at):
        """Zruší otevřený úkol; True, když ho zrušilo právě toto volání."""
        cursor = self.db.execute(
            "UPDATE heart_tasks SET status='cancelled', updated_at=? WHERE project_id=? AND id=?"
            " AND status IN ('ready','assigned')", (at, self.project, task_id))
        return cursor.rowcount == 1

    def reclaim(self, now):
        """Úkoly relací s prošlým nebo zneplatněným tokenem vrátí do `ready`; vrací jejich ID."""
        stale = ("SELECT id FROM gate_sessions WHERE (expires_at IS NOT NULL AND expires_at<=?)"
                 " OR revoked_at IS NOT NULL")
        rows = self.db.execute("SELECT id FROM heart_tasks WHERE project_id=? AND status='assigned' AND session_id IN ("
                               + stale + ") ORDER BY seq", (self.project, now)).fetchall()
        ids = [row[0] for row in rows]
        for task_id in ids:
            self.db.execute("UPDATE heart_tasks SET status='ready', session_id=NULL, updated_at=? WHERE project_id=?"
                            " AND id=?", (now, self.project, task_id))
        return ids
