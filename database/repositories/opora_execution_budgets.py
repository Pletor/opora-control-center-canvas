"""Caller-owned transactions for immutable budget policy and family consumption."""

import json

from backend.canvas.opora_change_validation import identifier, scope
from backend.canvas.opora_execution_budget_validation import policy
from backend.canvas.opora_hub_store import canonical, content_id
from database.repositories.opora_execution_budget_ledger import BudgetLedger
from database.repositories.opora_execution_budget_receipts import cancellation, policy_receipt


class Budgets(BudgetLedger):
    def __init__(self, db, project, workspace, node):
        scope({"project": project, "workspace": workspace})
        self.db, self.scope, self.node = db, (project, workspace), node

    def tx(self):
        if not self.db.in_transaction:
            raise RuntimeError("Budget writes require caller transaction.")

    def enrolled(self):
        row = self.db.execute(
            "SELECT first_policy_id FROM opora_execution_budget_enrollment WHERE project_id=? AND workspace_id=? AND node_id=?",
            (*self.scope, self.node),
        ).fetchone()
        if row:
            self.read_policy(row[0])
        elif (
            self.db.execute(
                "SELECT 1 FROM opora_execution_budget_policies WHERE project_id=? AND workspace_id=? AND node_id=? LIMIT 1",
                (*self.scope, self.node),
            ).fetchone()
            or self.db.execute(
                "SELECT 1 FROM opora_execution_budget_refs WHERE project_id=? AND workspace_id=? AND node_id=?",
                (*self.scope, self.node),
            ).fetchone()
        ):
            raise ValueError("Permanent budget enrollment authority is missing.")
        return bool(row)

    def read_policy(self, record_id):
        identifier(record_id)
        row = self.db.execute(
            "SELECT content FROM opora_execution_budget_policies WHERE project_id=? AND workspace_id=? AND node_id=? AND id=?",
            (*self.scope, self.node, record_id),
        ).fetchone()
        if not row:
            raise ValueError("Budget policy does not exist in this scope.")
        try:
            record = policy(json.loads(row[0]))
            self.integrity(record, record_id)
            return record
        except (KeyError, TypeError, AttributeError) as error:
            raise ValueError("Malformed stored budget policy.") from error

    def integrity(self, record, record_id):
        if (
            (record["project"], record["workspace"], record["nodeId"]) != (*self.scope, self.node)
            or record.get("id") != record_id
            or content_id({k: v for k, v in record.items() if k != "id"}) != record_id
        ):
            raise ValueError("Stored budget scope or hash mismatch.")

    def head(self):
        row = self.db.execute(
            "SELECT policy_id FROM opora_execution_budget_refs WHERE project_id=? AND workspace_id=? AND node_id=?",
            (*self.scope, self.node),
        ).fetchone()
        if row:
            self.read_policy(row[0])
            return row[0]
        if self.enrolled():
            raise ValueError("Enrolled budget policy authority is missing.")
        return None

    def activate(self, content, expected):
        self.tx()
        self.enrolled()
        policy(content)
        if self.head() != expected or content["parentPolicyHead"] != expected:
            raise ValueError("Budget policy head changed; refresh context.")
        record = {**content, "id": content_id(content)}
        self.db.execute(
            "INSERT INTO opora_execution_budget_policies VALUES(?,?,?,?,?)",
            (*self.scope, self.node, record["id"], canonical(record)),
        )
        self.db.execute(
            "INSERT INTO opora_execution_budget_refs VALUES(?,?,?,?) ON CONFLICT(project_id,workspace_id,node_id) DO UPDATE SET policy_id=excluded.policy_id",
            (*self.scope, self.node, record["id"]),
        )
        self.db.execute(
            "INSERT OR IGNORE INTO opora_execution_budget_enrollment VALUES(?,?,?,?)",
            (*self.scope, self.node, record["id"]),
        )
        return self.read_policy(record["id"])

    def replay(self, request, digest):
        try:
            return self._replay(request, digest)
        except (KeyError, TypeError, AttributeError) as error:
            raise ValueError("Malformed stored budget request receipt.") from error

    def _replay(self, request, digest):
        row = self.db.execute(
            "SELECT digest,result FROM opora_execution_budget_requests WHERE project_id=? AND workspace_id=? AND request_id=?",
            (*self.scope, request),
        ).fetchone()
        if not row:
            return None
        if row[0] != digest:
            raise ValueError("Budget request ID reused with different content.")
        result = json.loads(row[1])
        if result.get("policy"):
            policy_receipt(self, result)
            stored = self.read_policy(result["policy"]["id"])
            if stored != result["policy"]:
                raise ValueError("Budget policy replay integrity mismatch.")
        elif result.get("cancellation"):
            event = cancellation(self, result["cancellation"])
            stored = self.db.execute(
                "SELECT content FROM opora_execution_budget_cancels WHERE project_id=? AND workspace_id=? AND id=?",
                (*self.scope, event["id"]),
            ).fetchone()
            self.integrity(event, event["id"])
            if (
                set(result) != {"executionId", "state", "cancellation"}
                or not stored
                or json.loads(stored[0]) != event
                or event["requestId"] != request
                or event["requestDigest"] != digest
                or result["executionId"] != event["executionId"]
                or result["state"] != event["state"]
            ):
                raise ValueError("Budget cancellation replay integrity mismatch.")
        else:
            raise ValueError("Unknown stored budget request result.")
        return result

    def remember(self, request, digest, result):
        self.tx()
        self.db.execute(
            "INSERT INTO opora_execution_budget_requests VALUES(?,?,?,?,?)",
            (*self.scope, request, digest, canonical(result)),
        )

    def policies(self):
        rows = self.db.execute(
            "SELECT id FROM opora_execution_budget_policies WHERE project_id=? AND workspace_id=? AND node_id=? ORDER BY rowid DESC LIMIT 100",
            (*self.scope, self.node),
        ).fetchall()
        return [self.read_policy(row[0]) for row in rows]
