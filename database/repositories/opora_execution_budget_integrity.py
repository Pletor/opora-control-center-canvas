"""Cross-check every consumed ledger entry against durable executions; detect lost tails."""

import json

from backend.canvas.opora_execution_budget_validation import budget


def family_integrity(repo, accepted, events):
    rows = repo.db.execute(
        "SELECT id,record FROM opora_executions WHERE project_id=? AND workspace_id=? AND node_id=?",
        (*repo.scope, repo.node),
    ).fetchall()
    executions = {}
    for identifier, raw in rows:
        try:
            record = json.loads(raw)
            if record["acceptedRevision"] == accepted:
                if record["executionId"] != identifier or (
                    record["project"],
                    record["workspace"],
                    record["nodeId"],
                ) != (*repo.scope, repo.node):
                    raise ValueError("Family execution scope mismatch.")
                executions[identifier] = record
        except (KeyError, TypeError, AttributeError) as error:
            raise ValueError(
                "Malformed execution history during budget integrity validation."
            ) from error
    if set(executions) != {event["executionId"] for event in events}:
        raise ValueError("Budget ledger is incomplete or references missing executions.")
    for event in events:
        record = executions[event["executionId"]]
        if event["kind"] == "allocation":
            if (
                type(record.get("executionProtocolVersion")) is not int
                or record["executionProtocolVersion"] != 2
            ):
                raise ValueError("Budget allocation execution lost its v2 identity.")
            actual = budget(record.get("budget"))
            expected = {
                "policyHead": event["policyHead"],
                "familyId": event["familyId"],
                "allocationId": event["id"],
                "attempt": event["attempt"],
                "repairRound": event["repairRound"],
                "kind": event["runKind"],
                "admittedAt": event["admittedAt"],
                "runDeadlineAt": event["runDeadlineAt"],
                "maxRunSeconds": event["maxRunSeconds"],
            }
            if actual != expected:
                raise ValueError("Budget allocation and durable execution disagree.")
        elif record.get("executionProtocolVersion") == 2 or "budget" in record:
            raise ValueError("A v2 allocation cannot be disguised as legacy consumption.")
