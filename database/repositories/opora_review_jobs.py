"""Review jobs, leased worker tasks, posted findings and human decisions; callers own locks and transactions."""
import json

from backend.canvas.opora_hub_store import canonical

JOB = ("job_id", "execution_id", "node_id", "repository", "number", "base_sha", "head_sha", "round", "since_sha",
       "risk_tier", "risk", "required_approvals", "finders", "voters", "required_votes", "phase", "candidates",
       "created_at", "updated_at", "completed_at", "kind")
TASK = ("task_id", "job_id", "role", "slot", "state", "owner", "token", "epoch", "expires_at", "request_id",
        "digest", "submission", "submitted_at")
FINDING = ("finding_id", "repository", "number", "fingerprint", "job_id", "round", "head_sha", "severity", "status",
           "content", "resolution", "created_at", "updated_at")
JSON = {"risk", "candidates", "submission", "content", "resolution"}
TABLES = {"job": ("opora_review_jobs", JOB, "job_id"), "task": ("opora_review_tasks", TASK, "task_id"),
          "finding": ("opora_review_findings", FINDING, "finding_id")}


def _decode(columns, row):
    value = dict(zip(columns, row))
    for key in JSON & set(value):
        if value[key] is not None:
            value[key] = json.loads(value[key])
    return value


def _encode(key, value):
    return canonical(value) if key in JSON and value is not None else value


class ReviewJobs:
    def __init__(self, db, project, workspace):
        self.db, self.scope = db, (project, workspace)

    def _transaction(self):
        if not self.db.in_transaction:
            raise RuntimeError("Review job mutation requires caller transaction.")

    def _rows(self, kind, where="", parameters=()):
        table, columns, _ = TABLES[kind]
        cursor = self.db.execute(f"SELECT {','.join(columns)} FROM {table} WHERE project_id=? AND workspace_id=?"
                                 + where, (*self.scope, *parameters))
        return [_decode(columns, row) for row in cursor.fetchall()]

    def _one(self, kind, identifier):
        rows = self._rows(kind, f" AND {TABLES[kind][2]}=?", (identifier,))
        return rows[0] if rows else None

    def _insert(self, kind, row):
        self._transaction()
        table, columns, _ = TABLES[kind]
        values = [_encode(column, row.get(column)) for column in columns]
        marks = ",".join(["?"] * (len(columns) + 2))
        cursor = self.db.execute(f"INSERT OR IGNORE INTO {table}(project_id,workspace_id,{','.join(columns)}) "
                                 f"VALUES({marks})", (*self.scope, *values))
        return cursor.rowcount == 1

    def _update(self, kind, identifier, fields):
        self._transaction()
        table, columns, key = TABLES[kind]
        if set(fields) - set(columns) or key in fields:
            raise ValueError("Unknown review job fields.")
        assignments = ",".join(column + "=?" for column in fields)
        self.db.execute(f"UPDATE {table} SET {assignments} WHERE project_id=? AND workspace_id=? AND {key}=?",
                        (*(_encode(name, value) for name, value in fields.items()), *self.scope, identifier))
        return self._one(kind, identifier)

    # Jobs
    def job(self, job_id):
        return self._one("job", job_id)

    def jobs(self, limit=200):
        return self._rows("job", " ORDER BY created_at DESC, job_id LIMIT ?", (limit,))

    def jobs_for_pr(self, repository, number, kind="code"):
        """Jobs of one kind (`code` by default; `security` is its own round sequence)."""
        return self._rows("job", " AND repository=? AND number=? AND kind=? ORDER BY round, created_at, job_id",
                          (repository, number, kind))

    def insert_job(self, row):
        inserted = self._insert("job", {"kind": "code", **row})  # Older callers omit kind; NULL would be ignored.
        if inserted:
            self._round(self.job(row["job_id"]))
        return inserted

    def update_job(self, job_id, **fields):
        before = self.job(job_id) if "phase" in fields or "round" in fields else None
        after = self._update("job", job_id, fields)
        if before is not None and after is not None and (before["phase"], before["round"]) != (after["phase"], after["round"]):
            self._round(after)
        return after

    def _emit(self, kind, node, execution, number, data):
        # Outbox row in the caller's transaction.
        from backend.canvas.opora_events import emit_event
        emit_event(self.db, project_id=self.scope[0], workspace_id=self.scope[1], kind=kind, node_id=node,
                   execution_id=execution, pr_number=number, data=data)

    def _round(self, job):
        self._emit("review.round", job["node_id"], job["execution_id"], job["number"],
                   {"reviewJobId": job["job_id"], "kind": job["kind"], "round": job["round"], "phase": job["phase"],
                    "headSha": job["head_sha"], "riskTier": job["risk_tier"], "repository": job["repository"]})

    def _finding(self, finding):
        job = self.job(finding["job_id"]) or {}
        self._emit("review.finding", job.get("node_id"), job.get("execution_id"), finding["number"],
                   {"findingId": finding["finding_id"], "severity": finding["severity"], "status": finding["status"],
                    "round": finding["round"], "headSha": finding["head_sha"], "repository": finding["repository"]})

    # Tasks
    def task(self, task_id):
        return self._one("task", task_id)

    def tasks(self, job_id):
        return self._rows("task", " AND job_id=? ORDER BY role, slot", (job_id,))

    def insert_task(self, row):
        return self._insert("task", row)

    def update_task(self, task_id, **fields):
        return self._update("task", task_id, fields)

    def claimable(self, now, role=None):
        """Open tasks, or claimed tasks whose lease expired, of jobs still in the matching phase; oldest first."""
        sql = ("SELECT t.task_id FROM opora_review_tasks t JOIN opora_review_jobs j ON j.project_id=t.project_id "
               "AND j.workspace_id=t.workspace_id AND j.job_id=t.job_id WHERE t.project_id=? AND t.workspace_id=? "
               "AND ((t.role='finder' AND j.phase='find') OR (t.role='voter' AND j.phase='vote')) "
               "AND (t.state='open' OR (t.state='claimed' AND t.expires_at<=?))")
        parameters = [*self.scope, now]
        if role is not None:
            sql, parameters = sql + " AND t.role=?", [*parameters, role]
        rows = self.db.execute(sql + " ORDER BY j.created_at, j.job_id, t.role, t.slot", parameters).fetchall()
        return [row[0] for row in rows]

    def replay(self, owner, request_id):
        row = self.db.execute("SELECT digest,task_id FROM opora_review_task_requests WHERE project_id=? AND "
                              "workspace_id=? AND owner=? AND request_id=?", (*self.scope, owner, request_id)).fetchone()
        return (row[0], row[1]) if row else None

    def remember(self, owner, request_id, digest, task_id):
        self._transaction()
        self.db.execute("INSERT INTO opora_review_task_requests VALUES(?,?,?,?,?,?)",
                        (*self.scope, owner, request_id, digest, task_id))

    # Findings
    def finding(self, finding_id):
        return self._one("finding", finding_id)

    def findings_for_pr(self, repository, number):
        return self._rows("finding", " AND repository=? AND number=? ORDER BY round, created_at, finding_id",
                          (repository, number))

    def findings(self, limit=500):
        return self._rows("finding", " ORDER BY created_at DESC, finding_id LIMIT ?", (limit,))

    def insert_finding(self, row):
        inserted = self._insert("finding", row)
        if inserted:
            self._finding(self.finding(row["finding_id"]))
        return inserted

    def update_finding(self, finding_id, **fields):
        before = self.finding(finding_id) if "status" in fields else None
        after = self._update("finding", finding_id, fields)
        if before is not None and after is not None and before["status"] != after["status"]:
            self._finding(after)
        return after

    # Human decisions at the round cap
    def decision(self, repository, number, head_sha):
        row = self.db.execute("SELECT decision,reason,by,created_at FROM opora_review_decisions WHERE project_id=? "
                              "AND workspace_id=? AND repository=? AND number=? AND head_sha=?",
                              (*self.scope, repository, number, head_sha)).fetchone()
        return None if row is None else {"decision": row[0], "reason": row[1], "by": row[2], "createdAt": row[3]}

    def insert_decision(self, repository, number, head_sha, decision, reason, by, created_at):
        self._transaction()
        inserted = self.db.execute("INSERT OR IGNORE INTO opora_review_decisions VALUES(?,?,?,?,?,?,?,?,?)",
                                   (*self.scope, repository, number, head_sha, decision, reason, by,
                                    created_at)).rowcount == 1
        if inserted:
            from backend.canvas.opora_event_stage import nodes_of_pull_request
            for node in nodes_of_pull_request(self.db, *self.scope, number) or [None]:
                self._emit("decision.resolved", node, None, number,
                           {"decision": "review_round_cap", "resolution": decision, "headSha": head_sha,
                            "repository": repository})
        return inserted


def public_job(row, tasks=()):
    """Worker/consumer DTO; tokens never leave the claim/heartbeat responses."""
    return {"reviewJobId": row["job_id"], "kind": row["kind"], "executionId": row["execution_id"], "cardId": row["node_id"],
            "repository": row["repository"], "number": row["number"], "baseSha": row["base_sha"],
            "headSha": row["head_sha"], "round": row["round"], "sinceSha": row["since_sha"],
            "riskTier": row["risk_tier"], "risk": row["risk"], "requiredHumanApprovals": row["required_approvals"],
            "finders": row["finders"], "voters": row["voters"], "requiredVotes": row["required_votes"],
            "phase": row["phase"], "createdAt": row["created_at"], "completedAt": row["completed_at"],
            "tasks": [{"taskId": task["task_id"], "role": task["role"], "slot": task["slot"], "state": task["state"],
                       "epoch": task["epoch"]} for task in tasks]}


def public_finding(row):
    return {"findingId": row["finding_id"], "repository": row["repository"], "number": row["number"],
            "fingerprint": row["fingerprint"], "reviewJobId": row["job_id"], "round": row["round"],
            "headSha": row["head_sha"], "severity": row["severity"], "status": row["status"], **row["content"],
            "resolution": row["resolution"], "createdAt": row["created_at"], "updatedAt": row["updated_at"]}
