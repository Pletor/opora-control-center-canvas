"""Optional scoped native-operation receipts. Transaction boundaries belong to the caller."""
import hashlib
import json
import re

from backend.canvas.payload_errors import InvalidPayload, NextStep


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


class Receipt:
    def __init__(self, payload, kind, author):
        self.identifier = payload.get("operationId")
        if not isinstance(self.identifier, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", self.identifier):
            raise InvalidPayload("operationId must be 1-160 identifier characters.", field="operationId")
        self.scope = (payload["project"], payload["workspace"], kind, self.identifier)
        self.author = _json(author)
        self.digest = hashlib.sha256(_json(payload).encode()).hexdigest()

    def replay(self, db, *, allow_pending=False):
        row = db.execute("SELECT author,request_hash,status,response FROM canvas_operation_receipts WHERE "
                         "project_id=? AND workspace_id=? AND operation_kind=? AND operation_id=?", self.scope).fetchone()
        if row is None:
            return None
        if row[0] != self.author or row[1] != self.digest:
            raise NextStep("Operation ID is already bound to a different request or author.",
                           code="operation_conflict", hint="Use the original request and author, or a new operationId.")
        if row[2] != "complete":
            if allow_pending:
                return {"pending": json.loads(row[3]) if row[3] else None}
            raise NextStep("Operation has an incomplete write receipt; it must not be repeated blindly.",
                           code="operation_incomplete", hint="Read the Canvas and reconcile the pending operation before retrying.")
        return json.loads(row[3])

    def progress(self, db, prepared):
        db.execute("UPDATE canvas_operation_receipts SET response=? WHERE "
                   "project_id=? AND workspace_id=? AND operation_kind=? AND operation_id=? AND status='pending'",
                   (_json(prepared), *self.scope))

    def begin(self, db, prepared=None):
        db.execute("INSERT INTO canvas_operation_receipts VALUES(?,?,?,?,?,?,?,?)",
                   (*self.scope, self.author, self.digest, "pending", _json(prepared) if prepared is not None else None))

    def complete(self, db, response):
        db.execute("UPDATE canvas_operation_receipts SET status='complete',response=? WHERE "
                   "project_id=? AND workspace_id=? AND operation_kind=? AND operation_id=?",
                   (_json(response), *self.scope))
