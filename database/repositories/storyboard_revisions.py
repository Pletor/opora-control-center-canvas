"""Append-only native source, exact legacy import and explicit working-data export."""
import json
from backend.canvas.graph import valid_id

MAX_BYTES = 2 * 1024 * 1024


class StoryboardRevisions:
    def __init__(self, db, project, workspace, node):
        if not all(valid_id(value) for value in (project, workspace, node)):
            raise ValueError("Invalid storyboard source scope.")
        self.db, self.scope = db, (project, workspace, node)

    def latest(self):
        return self.db.execute("SELECT revision,record FROM storyboard_revisions WHERE project_id=? AND workspace_id=?"
                               " AND node_id=? ORDER BY revision DESC LIMIT 1", self.scope).fetchone()

    def read(self, revision=None):
        if revision is not None and (type(revision) is not int or revision < 0):
            raise ValueError("Invalid storyboard historical revision.")
        row = self.latest() if revision is None else self.db.execute(
            "SELECT revision,record FROM storyboard_revisions WHERE project_id=? AND workspace_id=? AND node_id=? AND revision=?",
            (*self.scope, revision)).fetchone()
        if row is None:
            if revision is not None:
                raise ValueError("Storyboard revision does not exist.")
            return {"revision": 0, "record": None, "storyboard": None}
        record = json.loads(row["record"]) if row["record"] is not None else None
        return {"revision": row["revision"], "record": record,
                "storyboard": None if record is None or record.get("deleted") else record}

    def insert(self, revision, record):
        if not self.db.in_transaction:
            raise RuntimeError("Storyboard history requires the caller's transaction.")
        if type(revision) is not int or revision < 0 or (record is not None and not isinstance(record, dict)):
            raise ValueError("Invalid storyboard source revision.")
        if record is not None and record.get("revision", revision) != revision:
            raise ValueError("Storyboard record and source revision differ.")
        raw = None if record is None else json.dumps(record, ensure_ascii=False, allow_nan=False)
        if raw is not None and len(raw.encode("utf-8")) > MAX_BYTES:
            raise ValueError("Storyboard source exceeds its byte limit.")
        self.db.execute("INSERT INTO storyboard_revisions VALUES(?,?,?,?,?)", (*self.scope, revision, raw))
        return self.read(revision)

    def import_legacy(self, path, prepare=None):
        """Idempotent under caller SQL transaction/lock; never write or remove the old file."""
        if self.latest() is not None:
            return self.read()
        if path.exists():
            if path.stat().st_size > MAX_BYTES:
                raise ValueError("Legacy storyboard exceeds its byte limit.")
            record = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(record, dict):
                raise ValueError("Invalid legacy storyboard record.")
            revision = record.get("revision", 0)
            if prepare is not None and not record.get("deleted"):
                prepare(record)
        else:
            record, revision = None, 0
        return self.insert(revision, record)

    def append(self, expected, record):
        current = self.read()
        if type(expected) is not int or expected != current["revision"]:
            raise ValueError("Storyboard source revision changed.")
        return self.insert(expected + 1, record)

    def export_legacy(self, path):
        """Explicit export to a caller-selected backup location; no database mutation."""
        value = self.read()
        if value["record"] is not None:
            if path.exists():
                raise ValueError("Storyboard export refuses to overwrite an existing file.")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value["record"], ensure_ascii=False, indent=2), encoding="utf-8")
        return {"project": self.scope[0], "workspace": self.scope[1], "nodeId": self.scope[2],
                "revision": value["revision"], "filePresent": value["record"] is not None}
