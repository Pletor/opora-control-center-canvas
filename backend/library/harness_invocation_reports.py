"""Read worker-reported metadata from native receipts; no parallel persistence or verification."""
import json

from backend.library.harness_invocations import validate_invocations
from database.repositories.opora_executions import Executions


def validate_result(result, record, repo):
    """Same invocation ID may be repeated unchanged, never reassigned to another observation."""
    items = validate_invocations(result, record)
    if not items:
        return
    rows = repo.db.execute(
        "SELECT record FROM opora_execution_results WHERE project_id=? AND workspace_id=?"
        " AND execution_id=? AND json_type(record,'$.result.harnessInvocations') IS NOT NULL"
        " ORDER BY rowid DESC LIMIT 129",
        (*repo.scope, record["executionId"])).fetchall()
    if len(rows) > 128:
        raise ValueError("Harness invocation receipt limit reached for this execution.")
    incoming = {item["invocationId"]: item for item in items}
    for row in rows:
        try:
            prior = validate_invocations(json.loads(row[0])["result"], record)
        except (ValueError, KeyError):
            continue  # Pre-extension unvalidated data cannot establish an observation.
        for item in prior:
            if item["invocationId"] in incoming and incoming[item["invocationId"]] != item:
                raise ValueError("Harness invocation identity was already used for different metadata.")


def read(db, project, workspace, *, node=None, resource=None, limit=50):
    """A bounded receipt window, explicitly not all-time rates or independent process observation."""
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Harness invocation receipt limit must be 1-100.")
    condition, params = "r.project_id=? AND r.workspace_id=?", [project, workspace]
    if node is not None:
        condition += " AND e.node_id=?"
        params.append(node)
    rows = db.execute(
        "SELECT r.execution_id,r.record FROM opora_execution_results r JOIN opora_executions e"
        " ON e.id=r.execution_id AND e.project_id=r.project_id AND e.workspace_id=r.workspace_id"
        " WHERE " + condition + " AND json_type(r.record,'$.result.harnessInvocations') IS NOT NULL"
        " ORDER BY r.rowid DESC LIMIT ?", (*params, limit + 1)).fetchall()
    observations, conflicted = {}, set()
    invalid = 0
    repo = Executions(db, project, workspace)
    for execution, raw in rows[:limit]:
        try:
            receipt, record = json.loads(raw), repo.read(execution)
            if receipt.get("assignmentDigest") != record["assignmentDigest"]:
                raise ValueError("Receipt assignment mismatch")
            items = validate_invocations(receipt["result"], record)
            source = receipt["receiptId"]
            if not isinstance(source, str) or not source or len(source) > 128:
                raise ValueError("Invalid native receipt identity")
            own = next(d for d in record["assignment"]["documents"] if d["nodeId"] == record["nodeId"])
            problems = own["fields"]["harness"]["problems"]
            if (not isinstance(problems, list) or not 1 <= len(problems) <= 8
                    or any(not isinstance(p, str) or not p or len(p) > 200 for p in problems)):
                raise ValueError("Invalid pinned problem cohort")
        except (ValueError, KeyError, StopIteration, TypeError):
            invalid += 1
            continue
        for item in items:
            key = execution, item["invocationId"]
            if key in conflicted:
                continue
            previous = observations.get(key)
            if previous:
                if previous[0] != item:
                    del observations[key]
                    conflicted.add(key)
                continue
            observations[key] = item, set(problems), record["nodeId"], source
    groups = {}
    for (execution, _), (item, problems, node_id, source) in observations.items():
        if resource is not None and item["resource"]["id"] != resource:
            continue
        for problem in problems:
            key = (item["resource"]["id"], item["resource"]["digest"], item["adapter"], item["nodeVersion"], problem)
            group = groups.setdefault(key, {"pass": 0, "fail": 0, "duration": 0.0,
                                           "outputBytes": 0, "executions": set(), "cards": set(),
                                           "latestSourceReceipt": source})
            group[item["outcome"]] += 1
            group["duration"] += item["durationMs"]
            group["outputBytes"] += item["outputBytes"]
            group["executions"].add(execution)
            group["cards"].add(node_id)
    cohorts = []
    for key, g in sorted(groups.items())[:100]:
        n = g["pass"] + g["fail"]
        cohorts.append({"resource": key[0], "digest": key[1], "adapter": key[2], "nodeVersion": key[3],
                        "problem": key[4], "invocations": n, "pass": g["pass"], "fail": g["fail"],
                        "percent": 100 * g["pass"] / n, "meanDurationMs": g["duration"] / n,
                        "outputBytes": g["outputBytes"], "executions": len(g["executions"]),
                        "tasks": len(g["cards"]), "latestSourceReceipt": g["latestSourceReceipt"]})
    return {"schema": "harness.invocations/1", "scope": {"project": project, "workspace": workspace, "nodeId": node},
            "authority": "native-result-receipts", "evidence": "worker-reported", "serverObserved": False,
            "independentlyVerified": False, "causalContribution": False, "promotionAllowed": False,
            "coverage": "bounded-newest-receipt-window; repeated calls are not independent trials",
            "scannedReceipts": min(len(rows), limit), "limited": len(rows) > limit or len(groups) > 100,
            "receiptWindowLimited": len(rows) > limit, "cohortsLimited": len(groups) > 100,
            "invalidReceipts": invalid, "conflictingInvocations": len(conflicted),
            "tokens": None, "cost": None, "cohorts": cohorts}
