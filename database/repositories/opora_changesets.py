"""Immutable specification records; transaction ownership stays with the caller."""
import json
import re

from backend.canvas.opora_hub_store import canonical, content_id


class ChangesetRepository:
    def __init__(self, db, project, workspace):
        self.db, self.scope = db, (project, workspace)

    def head(self):
        row = self.db.execute("SELECT accepted_id FROM opora_spec_refs WHERE project_id=? AND workspace_id=?",
                              self.scope).fetchone()
        return row[0] if row else None

    def read(self, identifier, *, proposal=False):
        if not isinstance(identifier, str) or not re.fullmatch(r"[a-f0-9]{40}", identifier):
            raise ValueError("Neplatné ID revize zadání.")
        table = "opora_spec_proposals" if proposal else "opora_spec_revisions"
        row = self.db.execute(f"SELECT content FROM {table} WHERE project_id=? AND workspace_id=? AND id=?",
                              (*self.scope, identifier)).fetchone()
        if row is None:
            raise ValueError("Revize zadání v tomto prostoru neexistuje.")
        record = json.loads(row[0])
        if (not isinstance(record, dict) or record.get("id") != identifier
                or (record.get("project"), record.get("workspace")) != self.scope
                or content_id({key: value for key, value in record.items() if key != "id"}) != identifier):
            raise ValueError("Otisk uložené revize zadání nesouhlasí.")
        return record

    def insert(self, content, *, proposal=False):
        if not self.db.in_transaction:
            raise RuntimeError("Changeset write requires an explicit transaction")
        record = {"id": content_id(content), **content}
        if proposal:
            self.db.execute("INSERT INTO opora_spec_proposals VALUES(?,?,?,?,?,?)",
                            (*self.scope, record["id"], content["parentRevision"], content["createdAt"], canonical(record)))
        else:
            self.db.execute("INSERT INTO opora_spec_revisions VALUES(?,?,?,?,?,?,?)",
                            (*self.scope, record["id"], content["parentRevision"], content["proposalId"],
                             content["createdAt"], canonical(record)))
        return record

    def advance(self, expected, identifier):
        if self.head() != expected:
            raise ValueError("Přijatá revize se změnila. Načtěte nový kontext.")
        if expected is None:
            self.db.execute("INSERT INTO opora_spec_refs VALUES(?,?,?)", (*self.scope, identifier))
        else:
            result = self.db.execute("UPDATE opora_spec_refs SET accepted_id=?"
                                     " WHERE project_id=? AND workspace_id=? AND accepted_id=?",
                                     (identifier, *self.scope, expected))
            if result.rowcount != 1:
                raise ValueError("Přijatá revize se změnila.")

    def accepted(self, identifier):
        return self.db.execute("SELECT 1 FROM opora_spec_revisions WHERE project_id=? AND workspace_id=? AND proposal_id=?",
                               (*self.scope, identifier)).fetchone() is not None

    def proposals(self, limit=100):
        rows = self.db.execute("SELECT id FROM opora_spec_proposals WHERE project_id=? AND workspace_id=?"
                               " ORDER BY created_at DESC,id DESC LIMIT ?", (*self.scope, limit)).fetchall()
        return [{**self.read(row[0], proposal=True), "accepted": self.accepted(row[0])} for row in rows]
