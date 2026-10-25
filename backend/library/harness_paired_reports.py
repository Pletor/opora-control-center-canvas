"""Bounded readback of reconciled paired claims from existing native result receipts."""
import json

from backend.library.harness_paired_results import validate_report
from database.repositories.opora_executions import Executions


def read(db, project, workspace, *, node=None, resource=None, problem=None, limit=20):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Harness paired receipt limit must be 1-100.")
    condition, params = "r.project_id=? AND r.workspace_id=?", [project, workspace]
    if node is not None:
        condition += " AND e.node_id=?"
        params.append(node)
    rows = db.execute(
        "SELECT r.execution_id,r.record FROM opora_execution_results r JOIN opora_executions e"
        " ON e.id=r.execution_id AND e.project_id=r.project_id AND e.workspace_id=r.workspace_id"
        " WHERE " + condition + " AND json_type(r.record,'$.result.harnessPairedEvaluation') IS NOT NULL"
        " ORDER BY r.rowid DESC LIMIT ?", (*params, limit + 1)).fetchall()
    repo = Executions(db, project, workspace)
    evaluations, conflicts, invalid = {}, set(), 0
    for execution, raw in rows[:limit]:
        try:
            receipt, record = json.loads(raw), repo.read(execution)
            if (receipt.get("executionId") != execution or record.get("executionId") != execution
                    or record.get("project") != project or record.get("workspace") != workspace
                    or receipt.get("assignmentDigest") != record.get("assignmentDigest")
                    or receipt.get("acceptedRevision") != record.get("acceptedRevision")
                    or receipt.get("state") != "reported"):
                raise ValueError("Invalid native paired receipt identity.")
            source = receipt["receiptId"]
            if (not isinstance(source, str) or not source or len(source) > 128
                    or any(ord(c) < 32 for c in source)):
                raise ValueError("Invalid native receipt source.")
            value = validate_report(receipt["result"], record)
            if value is None:
                raise ValueError("Missing paired report.")
        except (ValueError, KeyError, TypeError):
            invalid += 1
            continue
        key = execution, value["evaluationId"]
        if key in conflicts:
            continue
        previous = evaluations.get(key)
        if previous:
            if previous["report"] != value:
                del evaluations[key]
                conflicts.add(key)
            continue
        evaluations[key] = {"sourceReceipt": source, "report": value}
    # Filter after deduplication: a conflicting legacy identity must not survive by matching one side.
    items = [item for item in evaluations.values()
             if (problem is None or item["report"]["problem"] == problem)
             and (resource is None or resource in (item["report"]["baseline"]["id"], item["report"]["candidate"]["id"]))]
    return {"schema": "harness.paired-evaluations/1",
            "scope": {"project": project, "workspace": workspace, "nodeId": node},
            "authority": "native-result-receipts", "evidence": "worker-reported",
            "serverObserved": False, "independentlyVerified": False,
            "causalContribution": False, "promotionAllowed": False,
            "coverage": "bounded-newest-receipt-window; fixture cases and repeated evaluations are not independent production trials",
            "reviewDisposition": "not-projected; consult native exact-head review gate separately",
            "scannedReceipts": min(len(rows), limit), "receiptWindowLimited": len(rows) > limit,
            "invalidReceipts": invalid, "conflictingEvaluations": len(conflicts),
            "tokens": None, "cost": None, "evaluations": items}
