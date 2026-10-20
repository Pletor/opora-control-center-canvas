"""Append-only GitHub observations; callers own the project lock and transaction."""
import json
import re

from backend.canvas.opora_hub_store import canonical, content_id


class ReviewEvidenceRepository:
    def __init__(self, db, project, workspace):
        self.db, self.scope = db, (project, workspace)

    def read(self, identifier):
        if not isinstance(identifier, str) or not re.fullmatch(r"[a-f0-9]{40}", identifier):
            raise ValueError("Neplatné ID pozorování GitHubu.")
        row = self.db.execute("SELECT content,pr_number,observed_at FROM opora_review_evidence "
                              "WHERE project_id=? AND workspace_id=? AND id=?",
                              (*self.scope, identifier)).fetchone()
        if row is None:
            raise ValueError("Pozorování v tomto prostoru neexistuje.")
        try:
            record = json.loads(row[0])
        except (ValueError, TypeError):
            raise ValueError("Uložené pozorování je poškozené.") from None
        if (not isinstance(record, dict) or record.get("id") != identifier
                or (record.get("project"), record.get("workspace")) != self.scope
                or record.get("prNumber") != row[1] or record.get("observedAt") != row[2]
                or content_id({key: value for key, value in record.items() if key != "id"}) != identifier):
            raise ValueError("Otisk uloženého pozorování nesouhlasí.")
        return record

    def insert(self, content):
        if not self.db.in_transaction:
            raise RuntimeError("Evidence write requires an explicit transaction")
        if "id" in content or (content.get("project"), content.get("workspace")) != self.scope:
            raise ValueError("Pozorování nepatří do tohoto prostoru.")
        identifier = content_id(content)
        record = {**content, "id": identifier}
        self.db.execute("INSERT OR IGNORE INTO opora_review_evidence "
                        "(project_id,workspace_id,id,pr_number,observed_at,content) VALUES(?,?,?,?,?,?)",
                        (*self.scope, identifier, content["prNumber"], content["observedAt"], canonical(record)))
        return self.read(identifier)

    def iterate(self, limit=100):
        rows = self.db.execute("SELECT id FROM opora_review_evidence WHERE project_id=? AND workspace_id=? "
                               "ORDER BY observed_at DESC,rowid DESC LIMIT ?", (*self.scope, limit)).fetchall()
        for row in rows:
            yield self.read(row[0])

    def list(self, limit=100):
        return list(self.iterate(limit))

    def known_identity(self, number, repository, branch):
        rows = self.db.execute("SELECT id FROM opora_review_evidence WHERE project_id=? AND workspace_id=? "
                               "AND pr_number=? ORDER BY observed_at DESC,rowid DESC",
                               (*self.scope, number)).fetchall()
        for row in rows:
            record = self.read(row[0])
            if (record.get("complete") is True and record.get("configuredRepository") == repository
                    and record.get("configuredBaseBranch") == branch):
                return {"headSha": record["pr"]["headSha"], "repositoryId": record["repository"]["id"],
                        "prId": record["pr"]["id"]}
        return None
