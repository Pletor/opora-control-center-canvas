"""Durable documentation metadata uses native receipts, with no parallel event store."""
import json

from backend.library.harness_documentation import validate_documentation
from database.repositories.opora_executions import Executions


def validate_result(result, record, repo):
    items = validate_documentation(result, record)
    if not items:
        return
    rows = repo.db.execute(
        "SELECT record FROM opora_execution_results WHERE project_id=? AND workspace_id=? AND execution_id=?"
        " AND json_type(record,'$.result.harnessDocumentation') IS NOT NULL ORDER BY rowid DESC LIMIT 129",
        (*repo.scope, record["executionId"])).fetchall()
    if len(rows) > 128:
        raise ValueError("Harness documentation receipt limit reached.")
    incoming = {item["readId"]: item for item in items}
    for row in rows:
        try:
            prior = validate_documentation(json.loads(row[0])["result"], record)
        except (ValueError, KeyError, TypeError):
            continue
        for item in prior:
            if item["readId"] in incoming and incoming[item["readId"]] != item:
                raise ValueError("Harness documentation identity already has different metadata.")


def read(db, project, workspace, *, node=None, resource=None, limit=50):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Documentation receipt limit must be 1-100.")
    condition, params = "r.project_id=? AND r.workspace_id=?", [project, workspace]
    if node is not None:
        condition += " AND e.node_id=?"
        params.append(node)
    rows = db.execute(
        "SELECT r.execution_id,r.record FROM opora_execution_results r JOIN opora_executions e"
        " ON e.id=r.execution_id AND e.project_id=r.project_id AND e.workspace_id=r.workspace_id"
        " WHERE " + condition + " AND json_type(r.record,'$.result.harnessDocumentation') IS NOT NULL"
        " ORDER BY r.rowid DESC LIMIT ?", (*params, limit + 1)).fetchall()
    repo = Executions(db, project, workspace)
    observations, conflicts = {}, set()
    invalid = 0
    for execution, raw in rows[:limit]:
        try:
            receipt, record = json.loads(raw), repo.read(execution)
            if not isinstance(receipt, dict) or not isinstance(record, dict) or receipt.get("assignmentDigest") != record["assignmentDigest"]:
                raise ValueError("Wrong assignment")
            items = validate_documentation(receipt["result"], record)
            source = receipt["receiptId"]
            if not isinstance(source, str) or not 1 <= len(source) <= 128:
                raise ValueError("Invalid source")
        except (ValueError, KeyError, TypeError):
            invalid += 1
            continue
        for item in items:
            key = execution, item["readId"]
            if key in conflicts:
                continue
            previous = observations.get(key)
            if previous and previous["observation"] != item:
                del observations[key]
                conflicts.add(key)
            elif previous is None:
                observations[key] = {"observation": item, "sourceReceipt": source}
    selected = [entry for entry in observations.values()
                if resource is None or entry["observation"]["resource"]["id"] == resource]
    return {"schema": "harness.documentation-reads/1", "scope": {"project": project, "workspace": workspace, "nodeId": node},
            "authority": "native-result-receipts", "evidence": "worker-reported", "serverObserved": False,
            "independentlyVerified": False, "causalContribution": False, "promotionAllowed": False,
            "coverage": "submitted successful reads only; no failed-attempt denominator or task-success rate",
            "scannedReceipts": min(len(rows), limit), "invalidReceipts": invalid, "conflictingReads": len(conflicts),
            "receiptWindowLimited": len(rows) > limit, "observationsLimited": len(selected) > 100,
            "limited": len(rows) > limit or len(selected) > 100, "observations": selected[:100]}
