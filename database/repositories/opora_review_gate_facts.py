"""Self-check addenda and base observations of the merge gate; callers own locks and transactions."""
import json

from backend.canvas.opora_hub_store import canonical


class ReviewGateFacts:
    def __init__(self, db, project, workspace):
        self.db, self.scope = db, (project, workspace)

    def _transaction(self):
        if not self.db.in_transaction:
            raise RuntimeError("Review gate fact mutation requires caller transaction.")

    # Self-check evidence added after the execution result (one record per execution and head).
    def self_checks(self, execution_id):
        rows = self.db.execute("SELECT head_sha,record,by,created_at FROM opora_review_self_checks WHERE project_id=? "
                               "AND workspace_id=? AND execution_id=? ORDER BY created_at, rowid",
                               (*self.scope, execution_id)).fetchall()
        return [{"headSha": row[0], "selfChecks": json.loads(row[1]), "by": row[2], "createdAt": row[3]}
                for row in rows]

    def insert_self_checks(self, execution_id, head_sha, record, by, created_at):
        """First write per (execution, head) wins; returns False when a record already exists."""
        self._transaction()
        inserted = self.db.execute("INSERT OR IGNORE INTO opora_review_self_checks VALUES(?,?,?,?,?,?,?)",
                                   (*self.scope, execution_id, head_sha, canonical(record), by,
                                    created_at)).rowcount == 1
        if inserted:  # The merge gate may change: recompute the card's gate (docs/oporahub-events.md).
            from backend.canvas.opora_events import refresh_targets
            refresh_targets(self.db, *self.scope, execution_id=execution_id)
        return inserted

    # Latest read-only observation of a PR head against the base branch head and of the PR body.
    def base_observation(self, repository, number):
        row = self.db.execute("SELECT head_sha,observation,observed_at FROM opora_review_base_observations WHERE "
                              "project_id=? AND workspace_id=? AND repository=? AND number=?",
                              (*self.scope, repository, number)).fetchone()
        return None if row is None else {"headSha": row[0], **json.loads(row[1]), "observedAt": row[2]}

    def save_base_observation(self, repository, number, head_sha, observation, observed_at):
        self._transaction()
        self.db.execute("INSERT INTO opora_review_base_observations VALUES(?,?,?,?,?,?,?) ON CONFLICT(project_id,"
                        "workspace_id,repository,number) DO UPDATE SET head_sha=excluded.head_sha,"
                        "observation=excluded.observation,observed_at=excluded.observed_at",
                        (*self.scope, repository, number, head_sha, canonical(observation), observed_at))
        from backend.canvas.opora_events import refresh_targets
        refresh_targets(self.db, *self.scope, pr_number=number)
