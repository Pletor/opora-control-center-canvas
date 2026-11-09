"""Native vault operations with durable receipts and exact human intent review.

The existing handler owns validation, permissions and mutations. Receipt pending means
uncertain native completion, never permission to repeat a cross-storage operation.
"""
import json
from urllib.parse import urlencode

from backend.canvas.activity_log import HumanRequired, require_human
from backend.canvas.operation_receipts import Receipt
from backend.canvas.payload_errors import InvalidPayload, NextStep
from backend.editor.brief_vault.brief_vault import HUMAN_OPS, OPS, BriefVault, _payload
from backend.editor.brief_vault.operation_review_state import fingerprint, snapshot, verify_result

KIND = "brief_vault_routes.brief_vault_write"
DECISION = "brief-vault-operation-decision"


def _stored(db, project, workspace, kind, identifier):
    row = db.execute("SELECT status,response FROM canvas_operation_receipts WHERE project_id=? AND workspace_id=? "
                     "AND operation_kind=? AND operation_id=?", (project, workspace, kind, identifier)).fetchone()
    return {"status": row[0], "response": json.loads(row[1]) if row[1] else None} if row else None


def read(service, project, workspace, identifier):
    service.view(project, workspace)
    with service.reading(project):
        db = service.db_for(project)
        stored = _stored(db, project, workspace, KIND, identifier)
        if not stored or stored["status"] != "complete" or stored["response"].get("state") != "awaiting_human":
            raise NextStep("Exact vault human intent is unavailable.", code="vault_review_missing", hint="Read the original operation receipt.")
        item = stored["response"]["result"]
        decision = _stored(db, project, workspace, DECISION, identifier)
        return {**item, "decision": decision}


def _discard_unchanged(db, receipt, before, service, project, workspace):
    try:
        unchanged = snapshot(service, project, workspace) == before
    except Exception:  # noqa: BLE001 - failed reconciliation must retain pending
        unchanged = False
    if unchanged:
        with db:
            db.execute("DELETE FROM canvas_operation_receipts WHERE project_id=? AND workspace_id=? "
                       "AND operation_kind=? AND operation_id=? AND status='pending'", receipt.scope)
    return unchanged


def _prepare(db, receipt, before, operation, reason):
    project, workspace, _, identifier = receipt.scope
    intent = {"id": identifier, "operation": operation, "preimage": before, "digest": fingerprint(before),
              "by": json.loads(receipt.author), "reason": reason, "project": project, "workspace": workspace}
    query = {"screen": "canvas", "project": project, "workspace": workspace, "vaultReview": identifier}
    response = {"state": "awaiting_human", "verified": True, "reviewUrl": "/?" + urlencode(query), "result": intent}
    with db:
        receipt.begin(db)
        receipt.complete(db, response)
    if receipt.replay(db) != response:
        raise NextStep("Stored vault intent readback differs.", code="operation_incomplete", hint="Read the stored intent before retrying.")
    return response


def invoke(service, project, workspace, session, operation, request_id, *, review=False):
    if not isinstance(operation, dict) or set(operation) & {"project", "workspace", "actor", "agent", "by"}:
        raise InvalidPayload("Operation must not contain scope or author fields.", field="operation")
    if type(review) is not bool:
        raise InvalidPayload("review must be boolean.", field="review")
    if not isinstance(operation.get("op"), str) or operation["op"] not in OPS:
        raise InvalidPayload("Unknown native vault operation.", field="operation.op")
    payload = {"project": project, "workspace": workspace, **operation}
    _payload(payload)
    receipt = Receipt({**payload, "review": review, "operationId": request_id}, KIND,
                      {"kind": "agent", "name": session["worker_name"], "sessionId": session["id"]})
    with service.graph_lock_for(project), service.lock_for(project):
        db = service.db_for(project)
        replay = receipt.replay(db)
        if replay is not None:
            return replay
        before = snapshot(service, project, workspace)
        if before["readOnly"]:
            raise NextStep("Vault scope is read only.", code="vault_read_only", hint="Choose the writable scope.")
        placement = operation.get("op") == "gate" and operation.get("gate") == "placed" and operation.get("value") is True
        if review or operation["op"] in HUMAN_OPS or placement:
            return _prepare(db, receipt, before, operation, "Explicit native human review" if review else HUMAN_OPS.get(operation["op"], "Place the complete native vault plan after human review"))
        with db:
            receipt.begin(db, {"before": before})
        try:
            result = BriefVault(service).apply(payload, actor="agent", agent=session["worker_name"], duel_session=session)
            verify_result(service, project, workspace, result)
            after = snapshot(service, project, workspace)
            if after["specifications"]["acceptedHead"] != before["specifications"]["acceptedHead"]:
                raise NextStep("Vault operation changed accepted authority.", code="operation_incomplete", hint="Reconcile the native result.")
            response = {"state": "persisted", "verified": True, "result": result,
                        "acceptedHead": after["specifications"]["acceptedHead"], "stateDigest": fingerprint(after)}
            with db:
                receipt.complete(db, response)
            return response
        except HumanRequired as error:
            if not _discard_unchanged(db, receipt, before, service, project, workspace):
                raise NextStep(f"Vault operation {request_id} left uncertain native state at the human boundary.", code="operation_incomplete", hint=f"Read and reconcile pending operation {request_id} before review; do not repeat it blindly.") from error
            return _prepare(db, receipt, before, operation, str(error))
        except Exception as error:
            if not _discard_unchanged(db, receipt, before, service, project, workspace):
                raise NextStep(f"Vault operation {request_id} has an uncertain native result.",
                    code="operation_incomplete", hint=f"Read and reconcile pending operation {request_id}; do not repeat it blindly.") from error
            raise


def decide(service, project, workspace, identifier, digest, action, actor):
    require_human(actor, "Stored vault intent requires the actual human UI session.")
    if action not in ("accept", "reject"):
        raise InvalidPayload("Action must be accept or reject.", field="action")
    with service.graph_lock_for(project), service.lock_for(project):
        intent = read(service, project, workspace, identifier)
        if digest != intent["digest"]:
            raise NextStep("Intent digest differs.", code="vault_review_stale", hint="Read the exact stored intent.")
        db = service.db_for(project)
        receipt = Receipt({"project": project, "workspace": workspace, "operationId": identifier,
                           "action": action, "digest": digest}, DECISION, {"kind": "human", "name": "human"})
        replay = receipt.replay(db)
        if replay is not None:
            return replay
        before = snapshot(service, project, workspace)
        if action == "accept" and before != intent["preimage"]:
            raise NextStep("Native vault state changed since preparation.", code="vault_review_stale", hint="Prepare and review a new exact intent.")
        with db:
            receipt.begin(db, {"before": before})
        try:
            result = None if action == "reject" else BriefVault(service).apply(
                {"project": project, "workspace": workspace, **intent["operation"]}, actor="human")
            if result is not None:
                verify_result(service, project, workspace, result)
            after = snapshot(service, project, workspace)
            if after["specifications"]["acceptedHead"] != before["specifications"]["acceptedHead"]:
                raise NextStep("Vault operation unexpectedly changed accepted authority.", code="operation_incomplete", hint="Reconcile the native result.")
            response = {"status": "accepted" if action == "accept" else "rejected", "result": result,
                        "by": "human", "digest": digest, "stateDigest": fingerprint(after)}
            with db:
                receipt.complete(db, response)
            return response
        except Exception as error:
            # A placement may already have checkpointed version history.
            operation = intent["operation"]
            placement = operation["op"] == "gate" and operation.get("gate") == "placed" and operation.get("value") is True
            if placement or not _discard_unchanged(db, receipt, before, service, project, workspace):
                raise NextStep(f"Vault review operation {identifier} has an uncertain native result.",
                    code="operation_incomplete", hint=f"Read the exact review and reconcile pending operation {identifier}; do not repeat it blindly.") from error
            raise
