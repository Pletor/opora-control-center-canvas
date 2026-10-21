"""Budget admission and immutable deadline checks run inside execution transactions."""

from datetime import UTC, datetime

from backend.canvas.opora_execution_budget_clock import observe
from backend.canvas.opora_execution_budget_status import status
from backend.canvas.opora_execution_budget_validation import budget, execution_id
from database.repositories.opora_execution_budgets import Budgets

V2_FIELDS = {"expectedBudgetPolicyHead", "previousExecutionId"}


def enrolled(db, scope, node):
    return Budgets(db, *scope, node).enrolled()


def before_claim(db, scope, node, payload, accepted, now):
    repo = Budgets(db, *scope, node)
    v2 = bool(V2_FIELDS.intersection(payload))
    if not v2:
        if repo.enrolled():
            raise ValueError("This permanently enrolled card requires execution protocol v2.")
        return None
    if not V2_FIELDS.issubset(payload) or not repo.enrolled():
        raise ValueError("Execution protocol v2 requires an enrolled budget policy.")
    observe(db, now, scope[0])
    current = status(db, *scope, node, accepted)
    if current["blockedReason"]:
        raise ValueError(current["blockedReason"])
    if current["policyHead"] != payload["expectedBudgetPolicyHead"]:
        raise ValueError("Budget policy head changed before admission.")
    execution_id(payload["previousExecutionId"], nullable=True)
    if current["latestExecutionId"] != payload["previousExecutionId"]:
        raise ValueError("Budget predecessor is not the latest family execution.")
    return current


def allocate(db, scope, node, accepted, current, execution, now):
    observe(db, now, scope[0])
    policy = current["policy"]
    family = current["family"]
    kind = "repair" if family["hasReported"] else "retry" if family["attempts"] else "initial"
    attempt = family["attempts"] + 1
    repair = family["repairRounds"] + (kind == "repair")
    maximum = policy["limits"]["maxRunSeconds"]
    content = {
        "kind": "allocation",
        "executionId": execution,
        "runKind": kind,
        "attempt": attempt,
        "repairRound": repair,
        "previousExecutionId": family["lastExecutionId"],
        "policyHead": policy["id"],
        "policySnapshot": policy,
        "admittedAt": now,
        "runDeadlineAt": now + maximum,
        "maxRunSeconds": maximum,
        "createdAt": datetime.fromtimestamp(now, UTC).isoformat(),
    }
    record = Budgets(db, *scope, node).append(accepted, content)
    return budget(
        {
            "policyHead": policy["id"],
            "familyId": record["familyId"],
            "allocationId": record["id"],
            "attempt": attempt,
            "repairRound": repair,
            "kind": kind,
            "admittedAt": now,
            "runDeadlineAt": now + maximum,
            "maxRunSeconds": maximum,
        }
    )


def check(db, scope, record, now):
    version = record.get("executionProtocolVersion")
    if version is None and "budget" not in record:
        if enrolled(db, scope, record["nodeId"]):
            raise ValueError(
                "A legacy execution cannot retain authority on a budget-enrolled card."
            )
        return
    if type(version) is not int or version != 2:
        raise ValueError("Unsupported or malformed execution budget protocol.")
    value = budget(record["budget"])
    observe(db, now, scope[0])
    if now >= value["runDeadlineAt"]:
        raise ValueError("Execution run budget deadline has expired.")
    repo = Budgets(db, *scope, record["nodeId"])
    events = repo.events(record["acceptedRevision"])
    allocation = next((event for event in events if event["id"] == value["allocationId"]), None)
    if (
        not allocation
        or allocation["kind"] != "allocation"
        or allocation["executionId"] != record["executionId"]
    ):
        raise ValueError("Execution budget allocation is missing or belongs to another execution.")
    keys = {
        "policyHead": "policyHead",
        "familyId": "familyId",
        "attempt": "attempt",
        "repairRound": "repairRound",
        "kind": "runKind",
        "admittedAt": "admittedAt",
        "runDeadlineAt": "runDeadlineAt",
        "maxRunSeconds": "maxRunSeconds",
    }
    if any(value[key] != allocation[field] for key, field in keys.items()):
        raise ValueError("Execution budget differs from its immutable allocation.")
    if repo.read_policy(value["policyHead"]) != allocation["policySnapshot"]:
        raise ValueError("Execution budget policy snapshot integrity mismatch.")
