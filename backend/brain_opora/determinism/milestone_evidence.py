"""Read integration proof from existing accepted specifications and execution receipts.

Milestone criteria name positive and negative test steps explicitly. A reported boolean,
prototype approval, card closure or successful unrelated execution is never proof.
Evidence remains agent-reported, not independently verified by this read model.
"""
from backend.canvas.graph import digest, valid_id
from backend.canvas.opora_plan_steps import STEP_ID, validate_steps
from backend.canvas.opora_review_self_checks import NAME, validate_self_checks
from backend.canvas.opora_step_results import validate_step_results
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_executions import Executions
from backend.brain_opora.determinism.milestone_lineage import semantic_compatible


def descriptor(value):
    if not isinstance(value, dict) or set(value) != {"nodeId", "acceptedRevision", "positive", "negative"}:
        raise ValueError("verification requires nodeId, acceptedRevision, positive and negative.")
    if not valid_id(value["nodeId"]):
        raise ValueError("Invalid integration card identity.")
    for role in ("positive", "negative"):
        item = value[role]
        if not isinstance(item, dict) or set(item) != {"stepId", "check", "command"}:
            raise ValueError("Each integration case requires stepId, check and command.")
        if (not isinstance(item["stepId"], str) or not STEP_ID.fullmatch(item["stepId"])
                or not isinstance(item["check"], str) or not NAME.fullmatch(item["check"])
                or not isinstance(item["command"], str) or not item["command"].strip()
                or len(item["command"]) > 1000 or "\0" in item["command"]):
            raise ValueError("Invalid integration test reference or command.")
    if (value["positive"]["stepId"] == value["negative"]["stepId"]
            or value["positive"]["check"] == value["negative"]["check"]):
        raise ValueError("Positive and negative cases need distinct steps and checks.")
    return value


def accepted_steps(db, project, workspace, value):
    descriptor(value)
    repo = ChangesetRepository(db, project, workspace)
    semantic_compatible(db, project, workspace, value["acceptedRevision"], [value["nodeId"]])
    accepted = repo.read(value["acceptedRevision"])
    document = next((doc for doc in accepted["documents"] if doc["nodeId"] == value["nodeId"]), None)
    if document is None:
        raise ValueError("Integration card has no accepted specification.")
    steps = document["fields"].get("steps", [])
    validate_steps(steps)
    tests = {step["id"] for step in steps if step.get("kind") == "test"}
    if any(value[role]["stepId"] not in tests for role in ("positive", "negative")):
        raise ValueError("Integration cases must reference accepted test steps.")
    return accepted, document, steps


def validate_criteria(db, project, workspace, criteria):
    """Validate proposal references before activation; persist only references in existing criteria JSON."""
    pins, cases, names = set(), set(), set()
    for criterion in criteria:
        value = criterion.get("verification")
        if value is None:
            continue  # Legacy proposals can still be planned, but cannot verify a milestone.
        accepted_steps(db, project, workspace, value)
        semantic_compatible(db, project, workspace, value["acceptedRevision"], criterion["cards"])
        if value["nodeId"] not in criterion["cards"]:
            raise ValueError("The integration card must be among the criterion's referenced cards.")
        pins.add((value["nodeId"], value["acceptedRevision"]))
        for role in ("positive", "negative"):
            case = value[role]
            if case["stepId"] in cases or case["check"] in names:
                raise ValueError("Each criterion requires its own integration cases.")
            cases.add(case["stepId"]); names.add(case["check"])
    if len(pins) > 1:
        raise ValueError("All criteria must share one integration card and accepted revision.")


def _receipt(record, receipt, criteria, document, steps):
    if (receipt.get("executionId") != record["executionId"]
            or receipt.get("acceptedRevision") != record["acceptedRevision"]
            or receipt.get("assignmentDigest") != record["assignmentDigest"]):
        raise ValueError("Receipt does not match its pinned execution.")
    assignment = record["assignment"]
    pinned = next((doc for doc in assignment.get("documents", []) if doc.get("nodeId") == record["nodeId"]), None)
    if pinned != document or assignment.get("steps") != steps or digest(assignment) != record["assignmentDigest"]:
        raise ValueError("Execution assignment does not match the accepted integration specification.")
    result = receipt.get("result", {})
    checks = validate_self_checks(result.get("selfChecks"))
    by_name = {check["name"]: check for check in checks["checks"]}
    reports = {item["stepId"]: item for item in validate_step_results(result, steps)}
    for criterion in criteria:
        for role in ("positive", "negative"):
            case = criterion["verification"][role]
            report, check = reports.get(case["stepId"]), by_name.get(case["check"])
            if (not report or report["status"] != "done" or not check or check["status"] != "passed"
                    or check["exitCode"] != 0 or check["command"] != case["command"] or not check.get("output")
                    or case["check"] not in report["evidence"].get("checks", [])
                    or checks["headSha"] not in report["evidence"].get("commits", [])):
                raise ValueError("Positive or negative integration case has no matching passed run and output.")
    return {"status": "verified", "verified": True, "executionId": record["executionId"],
            "receiptId": receipt["receiptId"], "acceptedRevision": record["acceptedRevision"],
            "assignmentDigest": record["assignmentDigest"], "headSha": checks["headSha"],
            "source": "agent-reported execution receipt", "level": "reported_evidence", "independent": False}


def evaluate(db, project, workspace, criteria):
    missing = {"status": "missing", "verified": False, "reason": "integration_contract_missing",
               "level": "none", "independent": False}
    if not criteria or any(not item.get("verification") for item in criteria):
        return missing
    try:
        validate_criteria(db, project, workspace, criteria)
        value = criteria[0]["verification"]
        _, document, steps = accepted_steps(db, project, workspace, value)
        repo = Executions(db, project, workspace)
        records = repo.history(value["nodeId"])
        if not records:
            return {**missing, "reason": "integration_execution_missing"}
        # A newer failed/cancelled attempt supersedes an old green report.
        record = records[0]
        from backend.editor.research.execution_evidence import validate_assignment
        validate_assignment(db, project, workspace, record)
        if "storyboards" in record["assignment"]:
            from backend.canvas.storyboard_evidence import validate_db as validate_storyboards
            validate_storyboards(db, project, workspace, record["assignment"]["storyboards"])
        semantic_compatible(db, project, workspace, record["acceptedRevision"],
                            {card for criterion in criteria for card in criterion["cards"]})
        execution_spec = ChangesetRepository(db, project, workspace).read(record["acceptedRevision"])
        document = next(doc for doc in execution_spec["documents"] if doc["nodeId"] == value["nodeId"])
        if record.get("state") != "reported":
            return {"status": "pending", "verified": False, "reason": "integration_execution_not_reported"}
        receipts = repo.receipts(record["executionId"])
        if not receipts:
            return {**missing, "reason": "integration_receipt_missing"}
        return {**_receipt(record, receipts[-1], criteria, document, steps),
                "currentAcceptedRevision": ChangesetRepository(db, project, workspace).head()}
    except (ValueError, KeyError, TypeError) as error:
        return {"status": "unproven", "verified": False, "reason": "integration_evidence_mismatch", "detail": str(error)}
