import json
from datetime import UTC, datetime

EMPTY_FIELDS = {"goal": "", "non_goals": "", "acceptance": ""}


def validate_payload(payload):
    if not isinstance(payload, dict) or set(payload) != {
        "project",
        "workspace",
        "node",
        "expected_revision",
        "fields",
    }:
        raise ValueError("Neplatný formát zadání.")
    revision = payload["expected_revision"]
    if type(revision) is not int or revision < 0:
        raise ValueError("Neplatná očekávaná revize.")
    fields = payload["fields"]
    limits = {"goal": 4000, "non_goals": 8000, "acceptance": 12000}
    if not isinstance(fields, dict) or set(fields) != set(limits):
        raise ValueError("Zadání vyžaduje cíl, omezení a podmínky dokončení.")
    for key, limit in limits.items():
        if not isinstance(fields[key], str) or len(fields[key]) > limit or "\0" in fields[key]:
            raise ValueError("Neplatný text nebo překročený limit zadání.")


class NodeSpecStore:
    def __init__(self, canvas):
        self.canvas = canvas

    def read(self, scope):
        row = self.canvas.db_for(scope[0]).execute(
            "SELECT revision,fields,saved_at FROM node_spec_revisions WHERE project_id=? AND workspace_id=? AND node_id=? ORDER BY revision DESC LIMIT 1",
            scope,
        ).fetchone()
        if row is None:
            return {"revision": 0, "fields": dict(EMPTY_FIELDS), "saved_at": None}
        return {
            "revision": row["revision"],
            "fields": json.loads(row["fields"]),
            "saved_at": row["saved_at"],
        }

    def history(self, scope):
        rows = self.canvas.db_for(scope[0]).execute(
            "SELECT revision,fields,saved_at FROM node_spec_revisions WHERE project_id=? AND workspace_id=? AND node_id=? ORDER BY revision DESC LIMIT 21",
            scope,
        ).fetchall()
        return {
            "items": [
                {
                    "revision": row["revision"],
                    "fields": json.loads(row["fields"]),
                    "saved_at": row["saved_at"],
                }
                for row in rows[:20]
            ],
            "has_more": len(rows) > 20,
        }

    def save(self, scope, expected_revision, fields):
        db = self.canvas.db_for(scope[0])
        with db:
            db.execute("BEGIN IMMEDIATE")
            current = self.read(scope)
            if current["revision"] != expected_revision:
                raise ValueError(
                    "Konflikt: zadání se změnilo v jiném okně. Rozepsaný text zůstal zachován."
                )
            revision = current["revision"] + 1
            saved_at = datetime.now(UTC).isoformat()
            db.execute(
                "INSERT INTO node_spec_revisions VALUES(?,?,?,?,?,?)",
                (*scope, revision, json.dumps(fields, ensure_ascii=False), saved_at),
            )
        return {"revision": revision, "fields": fields, "saved_at": saved_at}
