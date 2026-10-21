"""Verified reviewer identities, incidents, reverts, eval cases and promoted checks.

Project-wide store (docs/oporahub-review-identity.md); callers own locks and transactions."""
import json

from backend.canvas.opora_hub_store import canonical

IDENTITY = ("identity_id", "name", "github_login", "github_user_id", "state", "operator", "nonce", "claimed_at",
            "verified_at", "revoked_at", "evidence")


def _identity(row):
    value = dict(zip(IDENTITY, row))
    value["operator"] = bool(value["operator"])
    value["evidence"] = json.loads(value["evidence"]) if value["evidence"] else None
    return value


class ReviewInsights:
    def __init__(self, db, project):
        self.db, self.project = db, project

    def _transaction(self):
        if not self.db.in_transaction:
            raise RuntimeError("Review insight mutation requires caller transaction.")

    # Identities
    def identities(self, where="", parameters=()):
        rows = self.db.execute("SELECT " + ",".join(IDENTITY) + " FROM opora_review_identities WHERE project_id=?"
                               + where + " ORDER BY claimed_at, identity_id", (self.project, *parameters)).fetchall()
        return [_identity(row) for row in rows]

    def identity(self, identity_id):
        rows = self.identities(" AND identity_id=?", (identity_id,))
        return rows[0] if rows else None

    def verified(self):
        return self.identities(" AND state='verified'")

    def save_identity(self, row):
        """Insert or fully replace one identity row (claim, re-claim, verify, revoke)."""
        self._transaction()
        values = [canonical(row[key]) if key == "evidence" and row[key] is not None else
                  int(row[key]) if key == "operator" else row[key] for key in IDENTITY]
        self.db.execute("INSERT OR REPLACE INTO opora_review_identities(project_id," + ",".join(IDENTITY)
                        + ") VALUES(" + ",".join("?" * (len(IDENTITY) + 1)) + ")", (self.project, *values))
        return self.identity(row["identity_id"])

    # Incidents and reverts
    def insert_incident(self, workspace, incident_id, repository, number, reference, summary, by, created_at):
        self._transaction()
        return self.db.execute("INSERT OR IGNORE INTO opora_review_incidents VALUES(?,?,?,?,?,?,?,?,?)",
                               (self.project, workspace, incident_id, repository, number, reference, summary, by,
                                created_at)).rowcount == 1

    def incidents(self):
        rows = self.db.execute("SELECT workspace_id,incident_id,repository,number,reference,summary,by,created_at "
                               "FROM opora_review_incidents WHERE project_id=? ORDER BY created_at,incident_id",
                               (self.project,)).fetchall()
        keys = ("workspace", "incidentId", "repository", "number", "reference", "summary", "by", "createdAt")
        return [dict(zip(keys, row)) for row in rows]

    def insert_revert(self, repository, number, revert_number, revert_sha, observed_at):
        self._transaction()
        return self.db.execute("INSERT OR IGNORE INTO opora_review_reverts VALUES(?,?,?,?,?,?)",
                               (self.project, repository, number, revert_number, revert_sha, observed_at)).rowcount == 1

    def reverts(self):
        rows = self.db.execute("SELECT repository,number,revert_number,revert_sha,observed_at FROM opora_review_reverts "
                               "WHERE project_id=? ORDER BY observed_at,repository,number,revert_number",
                               (self.project,)).fetchall()
        keys = ("repository", "number", "revertNumber", "revertSha", "observedAt")
        return [dict(zip(keys, row)) for row in rows]

    # Eval cases (immutable)
    def insert_case(self, workspace, case_id, repository, number, kind, source, content, created_at):
        self._transaction()
        return self.db.execute("INSERT OR IGNORE INTO opora_review_eval_cases VALUES(?,?,?,?,?,?,?,?,?)",
                               (self.project, workspace, case_id, repository, number, kind, source,
                                canonical(content), created_at)).rowcount == 1

    def cases(self, workspace=None):
        sql, parameters = "SELECT content FROM opora_review_eval_cases WHERE project_id=?", [self.project]
        if workspace is not None:
            sql, parameters = sql + " AND workspace_id=?", [*parameters, workspace]
        rows = self.db.execute(sql + " ORDER BY created_at,case_id", parameters).fetchall()
        return [json.loads(row[0]) for row in rows]

    # Promoted checks
    def promotion(self, bug_class):
        row = self.db.execute("SELECT check_ref,by,created_at FROM opora_review_promotions WHERE project_id=? AND "
                              "bug_class=?", (self.project, bug_class)).fetchone()
        return None if row is None else {"bugClass": bug_class, "checkRef": row[0], "by": row[1], "createdAt": row[2]}

    def promoted(self):
        return {row[0] for row in self.db.execute("SELECT bug_class FROM opora_review_promotions WHERE project_id=?",
                                                  (self.project,)).fetchall()}

    def insert_promotion(self, bug_class, check_ref, by, created_at):
        self._transaction()
        return self.db.execute("INSERT OR IGNORE INTO opora_review_promotions VALUES(?,?,?,?,?)",
                               (self.project, bug_class, check_ref, by, created_at)).rowcount == 1
