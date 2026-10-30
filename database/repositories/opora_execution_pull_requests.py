"""Execution -> PR links and loop-closure events; callers own locks and transactions."""
import json

from backend.canvas.opora_hub_store import canonical

STATES = ("open", "merged", "closed")
COLUMNS = ("execution_id", "node_id", "accepted_revision", "repository", "number", "head_ref", "head_sha",
           "state", "binding_id", "enrollment", "enrollment_error", "enrollment_retry_at", "enrollment_failures",
           "merge_sha", "merged_at", "awaiting_human_close", "attention", "source", "linked_by",
           "created_at", "updated_at")

# Czech text of each enrollment failure for people and agents reading the link (docs/oporahub-executions.md).
ENROLLMENT_MESSAGES = {
    "github-auth-missing": "GitHub odmítl přístup k repozitáři a Opora nemá token. Nastavte OPORA_GITHUB_TOKEN"
                           " (nebo GH_TOKEN / GITHUB_TOKEN) s právem číst tento repozitář a restartujte server;"
                           " sledování se pak zapne samo.",
    "github-auth-invalid": "GitHub odmítl token Opory (401, neplatný nebo prošlý). Nahraďte OPORA_GITHUB_TOKEN"
                           " (nebo GH_TOKEN / GITHUB_TOKEN) platným tokenem a restartujte server;"
                           " sledování se pak zapne samo.",
    "github-unavailable": "GitHub teď neodpovídá; Opora to zkusí znovu.",
    "github-not-configured": "Projekt nemá nastavený GitHub repozitář, sledování PR je vypnuté.",
}


def public(row):
    """Contract DTO (docs/oporahub-executions.md, "Uzavření smyčky"). A local merge (docs/lokalni-slouceni.md,
    `source: "local"`) has the same shape without a PR: `number` None, `repository` "local", plus `commit`."""
    value = _public(row)
    if row["source"] == "local":
        value |= {"number": None, "commit": row["merge_sha"]}
    return value


def _public(row):
    return {"executionId": row["execution_id"], "cardId": row["node_id"], "acceptedRevision": row["accepted_revision"],
            "repository": row["repository"], "number": row["number"], "headRef": row["head_ref"],
            "headSha": row["head_sha"], "state": row["state"], "bindingId": row["binding_id"],
            "enrollment": row["enrollment"], "enrollmentError": row["enrollment_error"],
            "enrollmentMessage": ENROLLMENT_MESSAGES.get(row["enrollment_error"]),
            "mergeSha": row["merge_sha"], "mergedAt": row["merged_at"],
            "awaitingHumanClose": bool(row["awaiting_human_close"]), "attention": row["attention"],
            # Merge write-back applied (execution.merged recorded, execution finished, card marked for human close).
            "planWrittenBack": row["state"] == "merged" and bool(row["awaiting_human_close"]),
            "source": row["source"], "createdAt": row["created_at"], "updatedAt": row["updated_at"]}


class ExecutionPullRequests:
    def __init__(self, db, project, workspace):
        self.db, self.scope = db, (project, workspace)

    def _transaction(self):
        if not self.db.in_transaction:
            raise RuntimeError("Execution PR mutation requires caller transaction.")

    def _rows(self, where, parameters):
        cursor = self.db.execute("SELECT " + ",".join(COLUMNS) + " FROM opora_execution_pull_requests "
                                 "WHERE project_id=? AND workspace_id=?" + where, (*self.scope, *parameters))
        return [dict(zip(COLUMNS, row)) for row in cursor.fetchall()]

    def read(self, execution_id):
        rows = self._rows(" AND execution_id=?", (execution_id,))
        return rows[0] if rows else None

    def listing(self, limit=200):
        return self._rows(" ORDER BY created_at DESC, execution_id LIMIT ?", (limit,))

    def unresolved(self, limit=100):
        """Links whose PR outcome can still change (closed PRs may be reopened)."""
        return self._rows(" AND state IN ('open','closed') ORDER BY updated_at, execution_id LIMIT ?", (limit,))

    def pending_enrollment(self, now, limit=10):
        return self._rows(" AND enrollment='pending' AND (enrollment_retry_at IS NULL OR enrollment_retry_at<=?)"
                          " ORDER BY enrollment_retry_at, execution_id LIMIT ?", (now, limit))

    def insert(self, row):
        self._transaction()
        values = [row[key] for key in COLUMNS]
        self.db.execute("INSERT INTO opora_execution_pull_requests(project_id,workspace_id," + ",".join(COLUMNS)
                        + ") VALUES(" + ",".join("?" * (len(COLUMNS) + 2)) + ")", (*self.scope, *values))
        return self.read(row["execution_id"])

    def update(self, execution_id, **fields):
        self._transaction()
        unknown = set(fields) - set(COLUMNS)
        if unknown or "execution_id" in fields:
            raise ValueError("Unknown execution PR link fields.")
        assignments = ",".join(key + "=?" for key in fields)
        self.db.execute("UPDATE opora_execution_pull_requests SET " + assignments
                        + " WHERE project_id=? AND workspace_id=? AND execution_id=?",
                        (*fields.values(), *self.scope, execution_id))
        return self.read(execution_id)

    def replay(self, request_id):
        row = self.db.execute("SELECT execution_id,digest FROM opora_execution_pull_request_requests "
                              "WHERE project_id=? AND workspace_id=? AND request_id=?", (*self.scope, request_id)).fetchone()
        return (row[0], row[1]) if row else None

    def remember(self, request_id, execution_id, digest):
        self._transaction()
        self.db.execute("INSERT INTO opora_execution_pull_request_requests VALUES(?,?,?,?,?)",
                        (*self.scope, request_id, execution_id, digest))

    def event(self, key, execution_id, kind, content, created_at):
        """Insert once per stable key; returns True when the event is new."""
        self._transaction()
        return self.db.execute("INSERT OR IGNORE INTO opora_execution_pull_request_events VALUES(?,?,?,?,?,?,?)",
                               (*self.scope, key, execution_id, kind, canonical(content), created_at)).rowcount == 1

    def events(self, execution_id):
        rows = self.db.execute("SELECT kind,content FROM opora_execution_pull_request_events WHERE project_id=? "
                               "AND workspace_id=? AND execution_id=? ORDER BY rowid", (*self.scope, execution_id)).fetchall()
        return [{"kind": row[0], **json.loads(row[1])} for row in rows]


def list_execution_pull_requests(db, project_id, workspace_id):
    """Read model for agent-state and other consumers: every link row with its PR state."""
    return [public(row) for row in ExecutionPullRequests(db, project_id, workspace_id).listing()]
