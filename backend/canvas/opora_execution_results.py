"""Idempotent reported evidence; never a card-completion mutation."""
import uuid

from backend.canvas.canvas_service import now
from backend.canvas.opora_change_validation import scope
from backend.canvas.opora_execution_validation import result_digest, validate
from backend.canvas.opora_executions import OporaExecutions


class ExecutionResults(OporaExecutions):
    def history(self, project, workspace, node=None):
        fields = {"project": project, "workspace": workspace}
        if node is not None:
            fields["nodeId"] = node
        validate(fields, {"nodeId"} if node is not None else set())
        with self.transaction(project, workspace) as repo:
            rows = repo.history(node)
            return {"executions": [{key: value for key, value in self.response(repo, record).items()
                                    if key not in ("token", "assignment")} for record in rows]}

    def receipts(self, identifier, project, workspace):
        scope({"project": project, "workspace": workspace})
        with self.transaction(project, workspace) as repo:
            return {"results": repo.receipts(identifier)}

    def submit(self, identifier, payload):
        project, workspace = validate(payload, {"token", "epoch", "requestId", "result"})
        fingerprint = result_digest(payload["result"])
        with self.transaction(project, workspace) as repo:
            record = repo.read(identifier)
            self.authenticate(record, payload["token"], payload["epoch"])
            prior = repo.receipt(identifier, payload["requestId"])
            if prior:
                if prior[0] != fingerprint:
                    raise ValueError("Result request identity was already used for different content.")
                return prior[1]
            self.active(repo, record)
            receipt = {"receiptId": uuid.uuid4().hex, "executionId": identifier,
                       "requestId": payload["requestId"], "result": payload["result"], "state": "reported",
                       "acceptedRevision": record["acceptedRevision"], "assignmentDigest": record["assignmentDigest"],
                       "verification": "agent-reported; not independently verified", "createdAt": now()}
            self.lease_valid(repo, record)
            import time

            from backend.canvas.opora_execution_budget_runtime import check
            check(repo.db, repo.scope, record, time.time())
            if record.get("executionProtocolVersion") == 2:
                receipt.update(executionProtocolVersion=2, budget=record["budget"])
            repo.insert_receipt(identifier, payload["requestId"], fingerprint, receipt)
            self.finish(repo, record, "reported")
            return receipt
