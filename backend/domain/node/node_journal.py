"""Deník jako datované bloky u stejného uzlu; není to druhý graf ani druhý lifecycle.

Zápis je vždy k jednomu dni a jednomu existujícímu uzlu, má revizi a CAS jako text uzlu.
Deník nemění stav práce ani nevytváří uzly.
"""
from datetime import UTC, date, datetime

from backend.domain.graph.graph import valid_id

FIELDS = {"project", "workspace", "node", "day", "expected_revision", "text"}


def valid_day(value):
    if not isinstance(value, str) or len(value) != 10:
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


class NodeJournal:
    def __init__(self, canvas):
        self.canvas = canvas
        canvas.db.execute("""CREATE TABLE IF NOT EXISTS node_journal_revisions(
            project_id TEXT, workspace_id TEXT, node_id TEXT, day TEXT, revision INTEGER,
            text TEXT NOT NULL, saved_at TEXT NOT NULL,
            PRIMARY KEY(project_id,workspace_id,node_id,day,revision))""")
        canvas.db.commit()

    def read(self, scope):
        row = self.canvas.db.execute(
            "SELECT revision,text,saved_at FROM node_journal_revisions WHERE project_id=? AND workspace_id=? AND node_id=? AND day=? ORDER BY revision DESC LIMIT 1",
            scope,
        ).fetchone()
        return dict(row) if row else {"revision": 0, "text": "", "saved_at": None}

    def days(self, project, workspace, node):
        rows = self.canvas.db.execute(
            "SELECT day,MAX(revision) AS revision,MAX(saved_at) AS saved_at FROM node_journal_revisions WHERE project_id=? AND workspace_id=? AND node_id=? GROUP BY day ORDER BY day DESC",
            (project, workspace, node),
        ).fetchall()
        return [dict(row) for row in rows]

    def access(self, project, workspace, node, day, payload=None):
        if payload is not None:
            if set(payload) != FIELDS:
                raise ValueError("Neplatný formát zápisu do deníku.")
            if type(payload["expected_revision"]) is not int or payload["expected_revision"] < 0:
                raise ValueError("Neplatná očekávaná revize zápisu.")
            text = payload["text"]
            if not isinstance(text, str) or len(text) > 64000 or "\0" in text:
                raise ValueError("Neplatný zápis nebo překročen limit 64000 znaků.")
        if not valid_day(day):
            raise ValueError("Neplatné datum zápisu; očekávám YYYY-MM-DD.")
        with self.canvas.graph_lock:
            view = self.canvas.view(project, workspace)
            if not valid_id(node) or not any(n["id"] == node for n in view["graph"]["nodes"]):
                raise ValueError("Uzel v tomto pracovním prostoru neexistuje.")
            if view["readOnly"]:
                raise ValueError("Main je pouze pro čtení; deník se píše v pracovním prostoru.")
            scope = (project, workspace, node, day)
            with self.canvas.lock:
                if payload is not None:
                    with self.canvas.db:
                        self.canvas.db.execute("BEGIN IMMEDIATE")
                        value = self.read(scope)
                        if value["revision"] != payload["expected_revision"]:
                            raise ValueError("Konflikt: zápis dne se změnil jinde. Rozepsaný text zůstal zachovaný.")
                        self.canvas.db.execute(
                            "INSERT INTO node_journal_revisions VALUES(?,?,?,?,?,?,?)",
                            (*scope, value["revision"] + 1, text, datetime.now(UTC).isoformat()),
                        )
                return {
                    **self.read(scope),
                    "days": self.days(project, workspace, node),
                    "readOnly": False,
                    "scope": {"project": project, "workspace": workspace, "node": node, "day": day},
                }
