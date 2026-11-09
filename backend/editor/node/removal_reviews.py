"""Scoped native working-operation reviews, backed by existing operation receipts.

Preparation never changes accepted authority. Interrupted native writes remain pending;
this layer does not pretend filesystem and registry operations form one transaction.
"""
import json
from contextlib import nullcontext
from urllib.parse import urlencode

from backend.canvas.operation_receipts import Receipt
from backend.canvas.payload_errors import NextStep
from backend.editor.node.removal_review_inputs import observe, verify

OPERATIONS = {"remove_item", "restore_removed", "graph"}


def _kind(operation, applying=False):
    if operation not in OPERATIONS:
        raise ValueError("Unknown native working operation.")
    return ("canvas-review-apply." if applying else "canvas-review.") + operation


def _receipt(project, workspace, operation, data, identifier, author, applying=False):
    return Receipt({"project": project, "workspace": workspace, "input": data, "operationId": identifier},
                   _kind(operation, applying), author)


def read(canvas, project, workspace, operation, identifier):
    with canvas.lock_for(project):
        db = canvas.db_for(project)
        row = db.execute("SELECT status,response FROM canvas_operation_receipts WHERE project_id=? AND workspace_id=? AND operation_kind=? AND operation_id=?",
                         (project, workspace, _kind(operation), identifier)).fetchone()
        if row is None:
            raise ValueError("Review not found in this project and workspace.")
        result = json.loads(row["response"]) if row["response"] else None
        applied = db.execute("SELECT status,response FROM canvas_operation_receipts WHERE project_id=? AND workspace_id=? AND operation_kind=? AND operation_id=?",
                             (project, workspace, _kind(operation, True), identifier)).fetchone()
        return {"project": project, "workspace": workspace, "operation": operation, "requestId": identifier,
                "status": row["status"], "preparation": result,
                "application": None if applied is None else {"status": applied["status"], "result": json.loads(applied["response"]) if applied["response"] else None}}


def _action(canvas, project, workspace, operation, data, actor):
    body = {"project": project, "workspace": workspace, **data}
    if operation == "remove_item":
        return canvas.removals.remove(body, actor=actor)
    if operation == "restore_removed":
        return canvas.removals.restore(body)
    return canvas.save_graph(project, workspace, data["graph"], data["digest"], undo=data["undo"], actor=actor)


def _apply(canvas, project, workspace, operation, reviewed, receipt, actor):
    db = canvas.db_for(project)
    with db:
        receipt.begin(db, {"review": reviewed})
    try:
        result = _action(canvas, project, workspace, operation, reviewed["input"], actor)
        verify(canvas, project, workspace, reviewed, result)
        response = {"state": "persisted", "verified": True, "acceptedHead": reviewed["acceptedHead"],
                    "acceptedPlanChanged": False, "result": result}
        with db:
            receipt.complete(db, response)
        return response
    except Exception as error:
        # Retry is safe only when the entire native preimage is still observable.
        try:
            unchanged = observe(canvas, project, workspace, operation, reviewed["input"]) == reviewed
        except Exception:
            unchanged = False
        if unchanged:
            with db:
                db.execute("DELETE FROM canvas_operation_receipts WHERE project_id=? AND workspace_id=? AND operation_kind=? AND operation_id=? AND status='pending'", receipt.scope)
        else:
            raise NextStep(f"Working operation {receipt.scope[3]} has an uncertain native result.",
                code="operation_incomplete", hint=f"Read and reconcile pending operation {receipt.scope[3]}; do not repeat it blindly.") from error
        raise


def prepare(canvas, project, workspace, operation, data, identifier, author):
    receipt = _receipt(project, workspace, operation, data, identifier, author)
    project_removal = operation == "remove_item" and data.get("kind") == "project"
    with canvas.git_lock if project_removal else nullcontext():
        with canvas.graph_lock_for(project), canvas.lock_for(project):
            db = canvas.db_for(project)
            replay = receipt.replay(db)
            if replay is not None:
                return replay
            reviewed = observe(canvas, project, workspace, operation, data)
            if operation == "graph" and reviewed["acceptedHead"] is not None:
                raise ValueError("Accepted graph updates require a native full candidate proposal.")
            if not reviewed["requiresHuman"]:
                return _apply(canvas, project, workspace, operation, reviewed, receipt, "agent")
            query = urlencode({"project": project, "workspace": workspace, "screen": "canvas", "environment": "project", "projectView": "library", "workingReview": identifier, "workingOperation": operation})
            response = {"state": "awaiting_human", "applied": False, "review": reviewed, "url": "/?" + query}
            with db:
                receipt.begin(db)
                receipt.complete(db, response)
            return response


def apply(canvas, project, workspace, operation, identifier, author):
    if author.get("kind") != "human":
        raise ValueError("Only a human may apply this review.")
    # Read only to choose lock order; the immutable preparation is read again under locks.
    initial = read(canvas, project, workspace, operation, identifier)["preparation"]
    project_removal = initial.get("review", {}).get("input", {}).get("kind") == "project"
    with canvas.git_lock if project_removal else nullcontext():
        with canvas.graph_lock_for(project), canvas.lock_for(project):
            saved = read(canvas, project, workspace, operation, identifier)
            prepared = saved["preparation"]
            if saved["status"] != "complete" or prepared.get("state") != "awaiting_human":
                raise ValueError("This operation is not awaiting human review.")
            reviewed = prepared["review"]
            receipt = _receipt(project, workspace, operation, reviewed, identifier, author, True)
            replay = receipt.replay(canvas.db_for(project))
            if replay is not None:
                return replay
            if observe(canvas, project, workspace, operation, reviewed["input"]) != reviewed:
                raise NextStep("Working state changed since preparation.", code="operation_conflict", hint="Prepare and review a fresh native operation.")
            return _apply(canvas, project, workspace, operation, reviewed, receipt, "human")
