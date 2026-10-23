"""Idempotent reported evidence; never a card-completion mutation."""
import uuid

from backend.canvas import opora_execution_decisions as execution_decisions
from backend.canvas import opora_step_results as step_results
from backend.canvas.canvas_service import now
from backend.canvas.opora_change_validation import scope
from backend.canvas.opora_execution_steps import reported_pairs
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
            steps = step_results.validate_step_results(payload["result"], record["assignment"].get("steps"))
            decisions = execution_decisions.validate_decisions(payload["result"])
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
            if record.get("contextProtocolVersion") == 2:
                from database.repositories.opora_execution_contexts import read_proof
                receipt.update(contextProtocolVersion=2,
                               contextValidation=read_proof(repo.db, *repo.scope, identifier))
            if decisions:  # stored as card decisions with this executionId (opora_execution_decisions.py)
                receipt["decisionIds"] = execution_decisions.store(self.canvas, repo.db, record, decisions)
            repo.insert_receipt(identifier, payload["requestId"], fingerprint, receipt)
            # Same transaction as the receipt; steps already announced by a checkpoint are not repeated.
            announced = reported_pairs(repo, identifier)
            step_results.emit_step_events(repo.db, record, [item for item in steps
                                                            if (item["stepId"], item["status"]) not in announced])
            self.finish(repo, record, "reported")
            from backend.canvas.opora_lease_events import reported
            reported(repo, record, receipt)
            return receipt
