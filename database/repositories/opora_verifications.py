"""Scoped immutable verification records; callers own the SQLite transaction."""
import hashlib
import json

from backend.canvas import opora_verification_validation as validation


class Verifications:
    def __init__(self, db, project, workspace):
        self.db, self.scope = db, (project, workspace)

    def read(self, identifier):
        row = self.db.execute("SELECT record FROM opora_verification_requests WHERE id=? AND project_id=? AND workspace_id=?",
                              (identifier, *self.scope)).fetchone()
        if row is None:
            raise ValueError("Verification does not exist in this scope.")
        record = json.loads(row[0])
        report = self.db.execute("SELECT record FROM opora_verification_reports WHERE verification_id=? AND project_id=? AND workspace_id=?",
                                 (identifier, *self.scope)).fetchone()
        return {**record, "report": json.loads(report[0]) if report else None}

    def replay(self, execution, request):
        row = self.db.execute("SELECT id,digest FROM opora_verification_requests WHERE project_id=? AND workspace_id=? AND execution_id=? AND request_id=?",
                              (*self.scope, execution, request)).fetchone()
        return (row[1], self.read(row[0])) if row else None

    def history(self, node=None):
        clause = " AND node_id=?" if node is not None else ""
        parameters = (*self.scope, node) if node is not None else self.scope
        rows = self.db.execute("SELECT id FROM opora_verification_requests WHERE project_id=? AND workspace_id=?"
                               + clause + " ORDER BY rowid DESC LIMIT 100", parameters).fetchall()
        return [self.read(row[0]) for row in rows]

    def blob(self, fingerprint, expected=None):
        row = self.db.execute("SELECT bytes,data FROM opora_verification_blobs WHERE project_id=? AND sha256=?",
                              (self.scope[0], fingerprint)).fetchone()
        if (row is None or len(row[1]) != row[0] or (expected is not None and row[0] != expected)
                or hashlib.sha256(row[1]).hexdigest() != fingerprint):
            raise ValueError("Verification artifact is missing or corrupt.")
        return row[1]

    def store_blobs(self, blobs):
        used = self.db.execute("SELECT COALESCE(SUM(bytes),0) FROM opora_verification_blobs WHERE project_id=?",
                               (self.scope[0],)).fetchone()[0]
        for fingerprint, data in blobs.items():
            exists = self.db.execute("SELECT 1 FROM opora_verification_blobs WHERE project_id=? AND sha256=?",
                                     (self.scope[0], fingerprint)).fetchone()
            if exists:
                self.blob(fingerprint, len(data))
                continue
            if len(data) > validation.FILE_LIMIT or hashlib.sha256(data).hexdigest() != fingerprint:
                raise ValueError("Verification blob hash or size mismatch.")
            used += len(data)
            if used > validation.PROJECT_LIMIT:
                raise ValueError("Verification project quota exceeds 64 MiB.")
            self.db.execute("INSERT INTO opora_verification_blobs VALUES(?,?,?,?)",
                            (self.scope[0], fingerprint, len(data), data))

    def insert(self, record):
        self.db.execute("INSERT INTO opora_verification_requests VALUES(?,?,?,?,?,?,?,?)",
                        (record["id"], *self.scope, record["nodeId"], record["executionId"], record["requestId"],
                         record["requestDigest"], json.dumps(record, ensure_ascii=False)))

    def insert_report(self, identifier, record):
        self.db.execute("INSERT INTO opora_verification_reports VALUES(?,?,?,?,?,?)",
                        (identifier, *self.scope, record["requestId"], record["reportDigest"], json.dumps(record, ensure_ascii=False)))
        # formal.result in the report's transaction
        from backend.canvas.opora_events import emit_event
        row = self.db.execute("SELECT node_id,execution_id FROM opora_verification_requests WHERE id=? AND project_id=?"
                              " AND workspace_id=?", (identifier, *self.scope)).fetchone()
        node, execution = (row[0], row[1]) if row else (None, None)
        outcome = record.get("outcome")
        emit_event(self.db, project_id=self.scope[0], workspace_id=self.scope[1], kind="formal.result", node_id=node,
                   execution_id=execution, data={"verificationId": identifier, "outcome": outcome})
        if outcome in ("counterexample", "failed"):
            emit_event(self.db, project_id=self.scope[0], workspace_id=self.scope[1], kind="decision.created",
                       node_id=node, execution_id=execution,
                       data={"decision": "verification_" + outcome, "verificationId": identifier})
