"""A human may revoke one matching capability even after clock failure or archive."""

from backend.canvas.opora_change_validation import scope
from backend.canvas.opora_changesets import stamp
from backend.canvas.opora_execution_budget_validation import execution_id, request_id
from backend.canvas.opora_hub_store import canonical, content_id
from backend.canvas.opora_review_policy import OporaReviewPolicy
from database.repositories.opora_execution_budgets import Budgets
from database.repositories.opora_executions import Executions


def cancel(service, identifier, payload, by):
    if not isinstance(payload, dict) or set(payload) != {
        "project",
        "workspace",
        "epoch",
        "requestId",
    }:
        raise ValueError("Invalid execution cancellation fields.")
    project, workspace = scope(payload)
    execution_id(identifier)
    request_id(payload["requestId"])
    if type(payload["epoch"]) is not int or payload["epoch"] < 1:
        raise ValueError("Invalid cancellation epoch.")
    author = OporaReviewPolicy.author(by)
    digest = content_id(
        {"executionId": identifier, "payload": payload, "by": author, "operation": "cancel"}
    )
    with service.graph_lock_for(project), service.lock_for(project):
        db = service.db_for(project)
        with db:
            db.execute("BEGIN IMMEDIATE")
            executions = Executions(db, project, workspace)
            record = executions.read(identifier)
            budgets = Budgets(db, project, workspace, record["nodeId"])
            replay = budgets.replay(payload["requestId"], digest)
            if replay:
                return replay
            if record["epoch"] != payload["epoch"]:
                raise ValueError("Cancellation epoch does not match this execution.")
            previous = record["state"]
            if previous == "running":
                db.execute(
                    "DELETE FROM card_leases WHERE project_id=? AND workspace_id=? AND node_id=? AND token=?",
                    (project, workspace, record["nodeId"], record["token"]),
                )
                record["state"] = "cancelled"
                executions.save(record)
            content = {
                "schemaVersion": 1,
                "project": project,
                "workspace": workspace,
                "nodeId": record["nodeId"],
                "executionId": identifier,
                "epoch": record["epoch"],
                "previousState": previous,
                "state": record["state"],
                "by": author,
                "createdAt": stamp(),
                "requestId": payload["requestId"],
                "requestDigest": digest,
            }
            event = {**content, "id": content_id(content)}
            db.execute(
                "INSERT INTO opora_execution_budget_cancels VALUES(?,?,?,?,?)",
                (project, workspace, event["id"], identifier, canonical(event)),
            )
            result = {"executionId": identifier, "state": record["state"], "cancellation": event}
            budgets.remember(payload["requestId"], digest, result)
            return result
