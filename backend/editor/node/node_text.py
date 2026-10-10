"""Text dokumentu sdílí identitu uzlu; žádný paralelní strom bloků."""
from datetime import UTC, datetime

from backend.canvas.graph import valid_id


def validate_payload(payload):
    """Tvar a limity zápisu textu uzlu; sdílí ho `/api/node-text` i dávka plánu. Vrací text."""
    if set(payload) != {"project", "workspace", "node", "expected_revision", "text"}:
        raise ValueError("Neplatný formát textu.")
    if type(payload["expected_revision"]) is not int or payload["expected_revision"] < 0:
        raise ValueError("Neplatná očekávaná revize textu.")
    text = payload["text"]
    if not isinstance(text, str) or len(text) > 64000 or "\0" in text:
        raise ValueError("Neplatný text nebo překročen limit 64000 znaků.")
    return text


class NodeTextStore:
    def __init__(self, canvas):
        self.canvas = canvas

    def read(self, scope):
        row = self.canvas.db_for(scope[0]).execute(
            "SELECT revision,text,saved_at FROM node_text_revisions WHERE project_id=? AND workspace_id=? AND node_id=? ORDER BY revision DESC LIMIT 1", scope
        ).fetchone()
        return dict(row) if row else {"revision": 0, "text": "", "saved_at": None}

    def read_all(self, project, workspace):
        """Poslední uložený text každého uzlu prostoru; podklad pro odkazy a zpětné odkazy."""
        rows = self.canvas.db_for(project).execute(
            "SELECT node_id,text FROM node_text_revisions AS t WHERE project_id=? AND workspace_id=? AND revision=(SELECT MAX(revision) FROM node_text_revisions WHERE project_id=t.project_id AND workspace_id=t.workspace_id AND node_id=t.node_id)",
            (project, workspace),
        ).fetchall()
        return {row["node_id"]: row["text"] for row in rows}

    def access(self, project, workspace, node, payload=None):
        if payload is not None:
            text = validate_payload(payload)
        with self.canvas.graph_lock_for(project):
            view = self.canvas.view(project, workspace)
            if not valid_id(node) or not any(n["id"] == node for n in view["graph"]["nodes"]):
                raise ValueError("Uzel v tomto pracovním prostoru neexistuje.")
            if view["readOnly"]:
                if payload is not None:
                    raise ValueError("Main je pouze pro čtení.")
                return {"revision": 0, "text": "", "saved_at": None, "readOnly": True, "available": False}
            scope = (project, workspace, node)
            with self.canvas.lock_for(project):
                if payload is not None:
                    db = self.canvas.db_for(project)
                    with db:
                        db.execute("BEGIN IMMEDIATE")
                        value = self.read(scope)
                        if value["revision"] != payload["expected_revision"]:
                            raise ValueError("Konflikt: text se změnil v jiném okně. Rozepsaný text zůstal zachován.")
                        db.execute("INSERT INTO node_text_revisions VALUES(?,?,?,?,?,?)", (*scope, value["revision"] + 1, text, datetime.now(UTC).isoformat()))
                return {**self.read(scope), "readOnly": False, "available": True}
