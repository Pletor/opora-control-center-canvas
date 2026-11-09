"""Scoped receipts around native operations; pending means reconcile, never repeat blindly."""
from backend.canvas.operation_receipts import Receipt
from backend.canvas.payload_errors import NextStep
from database.repositories.opora_changesets import ChangesetRepository


def run(service, project, workspace, session, capability, data, request_id, *, snapshot, action, verify):
    receipt = Receipt({"project": project, "workspace": workspace, **data, "operationId": request_id}, capability,
                      {"kind": "agent", "name": session["worker_name"]})
    with service.graph_lock_for(project), service.lock_for(project):
        db = service.db_for(project)
        replay = receipt.replay(db)
        if replay is not None:
            return replay
        before = snapshot()
        head = ChangesetRepository(db, project, workspace).head()
        with db:
            receipt.begin(db, {"before": before})
        returned = False
        try:
            result = action()
            returned = True
            after = snapshot()
            verify(before, after, result)
            if ChangesetRepository(db, project, workspace).head() != head:
                raise NextStep("Accepted authority changed during a draft write.", code="operation_incomplete", hint="Reconcile native state.")
            response = {"state": "persisted", "verified": True, "acceptedHead": head, "result": result}
            with db:
                receipt.complete(db, response)
            return response
        except Exception as error:
            # Validation failures with proven unchanged native stores remain retryable. Unknown partial
            # writes retain pending status; this journal does not claim Git/SQLite crash atomicity.
            try:
                unchanged = snapshot() == before
            except Exception:
                unchanged = False
            if unchanged and not returned:
                with db:
                    db.execute("DELETE FROM canvas_operation_receipts WHERE project_id=? AND workspace_id=? "
                               "AND operation_kind=? AND operation_id=? AND status='pending'", receipt.scope)
                raise
            # OP-B171BE.first-error: a native effect may already exist even on the first response.
            raise NextStep(f"Operation {request_id} may have changed native state; completion was not confirmed.",
                           code="operation_incomplete",
                           hint=f"Inspect native state and the pending receipt for {capability}, requestId {request_id}; "
                                "reconcile it before proceeding. Do not retry with a new requestId.") from error
