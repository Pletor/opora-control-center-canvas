import copy
import hashlib
import json
import sqlite3
from contextlib import nullcontext

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.editor.harness_invocation_routes import create_harness_invocation_router
from backend.library.harness_paired_reports import read
from backend.library.test_harness_paired_results import valid_report
from database.repositories.opora_executions import Executions
from database.schema.opora_execution_schema import SCHEMA


def database():
    db = sqlite3.connect(":memory:")
    db.executescript(SCHEMA)
    return db


def save(db, record, result, request, *, source=None, assignment_digest=None, accepted_revision=None):
    repo = Executions(db, record["project"], record["workspace"])
    try:
        repo.read(record["executionId"])
    except ValueError:
        repo.insert(record, "agent:test", "claim-" + record["executionId"], "request-digest")
    receipt = {"receiptId": source or request, "executionId": record["executionId"],
        "requestId": request, "result": result,
        "assignmentDigest": assignment_digest or record["assignmentDigest"],
        "acceptedRevision": accepted_revision or record["acceptedRevision"], "state": "reported"}
    repo.insert_receipt(record["executionId"], request, request, receipt)
    return receipt


def rebind(record, result, execution, *, project=None, workspace=None, node=None):
    record, result = copy.deepcopy(record), copy.deepcopy(result)
    old = record["nodeId"]
    record.update(executionId=execution, project=project or record["project"],
                  workspace=workspace or record["workspace"], nodeId=node or old)
    for document in record["assignment"]["documents"]:
        if document["nodeId"] == old:
            document["nodeId"] = record["nodeId"]
    value = result["harnessPairedEvaluation"]
    value["execution"].update({key: record[key] for key in value["execution"]})
    for item in result["harnessInvocations"]:
        item["execution"].update({key: record[key] for key in item["execution"]})
    for item in result["harnessPairedEvaluation"].get("harnessInvocations", []):
        item["execution"].update({key: record[key] for key in item["execution"]})
    return record, result


def problem_variant(record, result, problem):
    record, result = copy.deepcopy(record), copy.deepcopy(result)
    resource = next(item for doc in record["assignment"]["documents"]
                    for item in (doc.get("fields", {}).get("harness", {}).get("resources", []))
                    if item["category"] == "testing")
    plan = json.loads(resource["content"])
    plan["problem"] = problem
    resource["content"] = json.dumps(plan, separators=(",", ":"))
    resource["digest"] = hashlib.sha256(resource["content"].encode()).hexdigest()
    result["harnessPairedEvaluation"]["plan"]["digest"] = resource["digest"]
    result["harnessPairedEvaluation"]["problem"] = problem
    return record, result


def test_readback_deduplicates_full_and_projected_and_redacts_private_fields():
    db = database()
    record, result = valid_report()
    result.update(stdout="private stdout", token="private token")
    save(db, record, result, "r1", source="source-one")
    projected = copy.deepcopy(result)
    projected["harnessPairedEvaluation"].pop("harnessInvocations")
    save(db, record, projected, "r2", source="source-two")
    report = read(db, record["project"], record["workspace"])
    assert report["scannedReceipts"] == 2 and len(report["evaluations"]) == 1
    item = report["evaluations"][0]
    assert item["sourceReceipt"] == "source-two"
    assert item["report"]["evaluationId"] == result["harnessPairedEvaluation"]["evaluationId"]
    assert all(report[key] is False for key in ("independentlyVerified", "causalContribution", "promotionAllowed"))
    encoded = json.dumps(report)
    assert "private stdout" not in encoded and "private token" not in encoded
    assert "args" not in encoded and "expectedStdout" not in encoded


def test_conflicting_valid_evaluation_identity_excludes_both_receipts():
    db = database()
    record, first = valid_report()
    second_record, second = valid_report({(case, side): "pass" for case in ("case:a", "case:b", "case:c")
                                         for side in ("baseline", "candidate")})
    second["harnessPairedEvaluation"]["evaluationId"] = first["harnessPairedEvaluation"]["evaluationId"]
    save(db, record, first, "r1")
    save(db, second_record, second, "r2")
    report = read(db, record["project"], record["workspace"])
    assert report["evaluations"] == [] and report["conflictingEvaluations"] == 1


def test_invalid_historical_receipt_is_counted_and_ignored():
    db = database()
    record, result = valid_report()
    save(db, record, result, "valid")
    save(db, record, result, "invalid", assignment_digest="wrong")
    save(db, record, result, "invalid-revision", accepted_revision="0" * 40)
    report = read(db, record["project"], record["workspace"])
    assert report["invalidReceipts"] == 2 and len(report["evaluations"]) == 1


def test_scope_node_resource_and_problem_filters_are_isolated():
    db = database()
    record, result = valid_report()
    save(db, record, result, "r1")
    other, other_result = rebind(record, result, "exec-2", node="node-2")
    save(db, other, other_result, "r2")
    accepted, accepted_result = rebind(record, result, "exec-3", workspace="accepted")
    save(db, accepted, accepted_result, "r3")
    foreign, foreign_result = rebind(record, result, "exec-4", project="foreign")
    save(db, foreign, foreign_result, "r4")
    report = read(db, record["project"], record["workspace"])
    assert len(report["evaluations"]) == 2, report
    assert len(read(db, record["project"], record["workspace"], node="node-2")["evaluations"]) == 1
    assert len(read(db, record["project"], "accepted")["evaluations"]) == 1
    assert read(db, record["project"], record["workspace"], node="missing")["evaluations"] == []
    assert read(db, record["project"], record["workspace"], resource="script:absent")["evaluations"] == []
    assert read(db, record["project"], record["workspace"], problem="other.problem")["evaluations"] == []
    assert len(read(db, "foreign", record["workspace"])["evaluations"]) == 1


def test_newest_receipt_window_is_applied_before_problem_filter():
    db = database()
    record, result = valid_report()
    save(db, record, result, "matching-old")
    newer, newer_result = problem_variant(record, result, "different.problem")
    newer, newer_result = rebind(newer, newer_result, "exec-newer")
    save(db, newer, newer_result, "filtered-new")
    unfiltered = read(db, record["project"], record["workspace"], limit=1)
    assert unfiltered["invalidReceipts"] == 0
    assert unfiltered["evaluations"][0]["report"]["problem"] == "different.problem"
    report = read(db, record["project"], record["workspace"], problem="numeric.identity", limit=1)
    assert report["scannedReceipts"] == 1 and report["receiptWindowLimited"] is True
    assert report["evaluations"] == []


@pytest.mark.parametrize("limit", [0, 101, True])
def test_read_limit_is_bounded(limit):
    with pytest.raises(ValueError, match="limit"):
        read(database(), "p", "w", limit=limit)


class Canvas:
    def __init__(self, db):
        self.db = db

    def project_exists(self, project):
        return project == "p"

    def lock_for(self, _project):
        return nullcontext()

    def db_for(self, _project):
        return self.db


def test_http_route_has_one_prefix_and_validates_scope_limit_and_method():
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.executescript(SCHEMA)
    record, result = valid_report()
    save(db, record, result, "r1")
    app = FastAPI()
    app.include_router(create_harness_invocation_router(Canvas(db)))
    with TestClient(app) as client:
        response = client.get("/api/oporahub/harness-paired-evaluations",
                              params={"project": record["project"], "workspace": record["workspace"]})
        assert response.status_code == 200 and len(response.json()["evaluations"]) == 1
        assert client.get("/api/oporahub/harness-invocations/harness-paired-evaluations",
                          params={"project": record["project"], "workspace": record["workspace"]}).status_code == 404
        assert client.get("/api/oporahub/harness-paired-evaluations",
                          params={"project": "missing", "workspace": "draft"}).status_code == 404
        assert client.get("/api/oporahub/harness-paired-evaluations",
                          params={"project": record["project"], "workspace": record["workspace"], "limit": 0}).status_code == 422
        assert client.post("/api/oporahub/harness-paired-evaluations").status_code == 405
