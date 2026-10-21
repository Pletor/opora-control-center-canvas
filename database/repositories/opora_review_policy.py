"""Scoped immutable policy history; activation CAS belongs to the caller's transaction."""
import json

from backend.canvas.opora_change_validation import identifier, scope
from backend.canvas.opora_hub_store import canonical, content_id
from backend.canvas.opora_review_policy_validation import validate_policy


class Policies:
    def __init__(self, db, project, workspace):
        scope({"project": project, "workspace": workspace})
        self.db, self.scope = db, (project, workspace)

    def read(self, record_id):
        identifier(record_id)
        row = self.db.execute("SELECT content,parent_id,created_at FROM opora_review_policies "
                              "WHERE project_id=? AND workspace_id=? AND id=?", (*self.scope, record_id)).fetchone()
        if row is None:
            raise ValueError("Policy revision does not exist in this scope.")
        try:
            record = json.loads(row[0])
            validate_policy(record)
            if (record.get("id") != record_id or (record["project"], record["workspace"]) != self.scope
                    or record["parentPolicyRevision"] != row[1] or record["createdAt"] != row[2]
                    or content_id({key: value for key, value in record.items() if key != "id"}) != record_id):
                raise ValueError("Policy revision integrity mismatch.")
            return record
        except (TypeError, KeyError, AttributeError, json.JSONDecodeError) as error:
            raise ValueError("Malformed stored review policy.") from error

    def head(self):
        row = self.db.execute("SELECT policy_id FROM opora_review_policy_refs WHERE project_id=? AND workspace_id=?", self.scope).fetchone()
        if row is None:
            return None
        self.read(row[0])
        return row[0]

    def activate(self, content, expected_head):
        if not self.db.in_transaction:
            raise RuntimeError("Policy activation requires an explicit transaction.")
        identifier(expected_head, nullable=True)
        validate_policy(content)
        if "id" in content or (content["project"], content["workspace"]) != self.scope or content["parentPolicyRevision"] != expected_head:
            raise ValueError("Policy scope or parent does not match activation.")
        if self.head() != expected_head:
            raise ValueError("Policy head changed; refresh before configuring policy.")
        if expected_head is None and not content["enabled"]:
            raise ValueError("Cannot disable a policy that does not exist.")
        if not content["enabled"]:
            previous = self.read(expected_head)
            if not previous["enabled"] or any(content[key] != previous[key] for key in ("repository", "identityEvidenceId", "rules")):
                raise ValueError("Disabled revision must retain the preceding policy bindings.")
        record = {**content, "id": content_id(content)}
        self.db.execute("INSERT OR IGNORE INTO opora_review_policies VALUES(?,?,?,?,?,?)",
                        (*self.scope, record["id"], expected_head, record["createdAt"], canonical(record)))
        if self.read(record["id"]) != record:
            raise ValueError("Policy revision identity conflict.")
        if expected_head is None:
            self.db.execute("INSERT INTO opora_review_policy_refs VALUES(?,?,?)", (*self.scope, record["id"]))
        else:
            changed = self.db.execute("UPDATE opora_review_policy_refs SET policy_id=? WHERE project_id=? AND workspace_id=? AND policy_id=?",
                                      (record["id"], *self.scope, expected_head))
            if changed.rowcount != 1:
                raise ValueError("Policy head changed during activation.")
        return record

    def history(self):
        rows = self.db.execute("SELECT id FROM opora_review_policies WHERE project_id=? AND workspace_id=? "
                              "ORDER BY rowid DESC LIMIT 100", self.scope).fetchall()
        return [self.read(row[0]) for row in rows]
