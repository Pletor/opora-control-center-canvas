import copy
import json
import sqlite3
import uuid

import pytest

from backend.canvas.opora_result_extensions import validate_extensions
from backend.library.harness_invocation_reports import read
from backend.library.test_harness_invocations import fixture
from database.repositories.opora_executions import Executions
from database.schema.opora_execution_schema import SCHEMA


def database():
    db = sqlite3.connect(":memory:")
    db.executescript(SCHEMA)
    return db


def save(db, record, request, items, *, source=None, digest=None):
    repo = Executions(db, record["project"], record["workspace"])
    try:
        repo.read(record["executionId"])
    except ValueError:
        repo.insert(record, "agent:test", request, "request-digest")
    result = {"summary": "ok", "stdout": "private output", "token": "private token",
              "harnessInvocations": items}
    receipt = {"receiptId": source or uuid.uuid4().hex, "executionId": record["executionId"],
               "requestId": request, "result": result, "assignmentDigest": digest or record["assignmentDigest"],
               "state": "reported", "verification": "agent-reported; not independently verified"}
    repo.insert_receipt(record["executionId"], request, request, receipt)
    return repo


def test_native_receipts_count_repeated_invocation_once_and_hide_raw_fields():
    db = database()
    record, item = fixture()
    repo = save(db, record, "r1", [item])
    validate_extensions({"summary": "again", "harnessInvocations": [item]}, record, repo)
    save(db, record, "r2", [copy.deepcopy(item)])
    report = read(db, record["project"], record["workspace"])
    assert report["authority"] == "native-result-receipts"
    assert report["evidence"] == "worker-reported" and report["serverObserved"] is False
    assert report["independentlyVerified"] is False and report["promotionAllowed"] is False
    assert report["cohorts"][0]["invocations"] == 1
    assert report["cohorts"][0]["meanDurationMs"] == item["durationMs"]
    encoded = json.dumps(report)
    assert "private output" not in encoded and "private token" not in encoded
    def keys(value):
        if isinstance(value, dict):
            return set(value) | set().union(*(keys(child) for child in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(child) for child in value))
        return set()
    assert "stdout" not in keys(report) and "token" not in keys(report)


def test_validation_rejects_conflicting_id_and_read_excludes_historical_conflict():
    db = database()
    record, item = fixture()
    repo = save(db, record, "r1", [item])
    changed = copy.deepcopy(item)
    changed["durationMs"] += 1
    with pytest.raises(ValueError, match="identity was already used"):
        validate_extensions({"harnessInvocations": [changed]}, record, repo)
    save(db, record, "r2", [changed])  # Simulates a pre-validator/bypassed legacy receipt.
    report = read(db, record["project"], record["workspace"])
    assert report["cohorts"] == []
    assert report["conflictingInvocations"] == 1


def test_scope_node_resource_and_changed_digest_are_isolated():
    db = database()
    record, item = fixture()
    save(db, record, "r1", [item])
    other, item2 = fixture()
    other.update(project="another", executionId="exec-2", nodeId="node-2")
    item2["execution"].update(project="another", executionId="exec-2", nodeId="node-2")
    other["assignment"]["documents"][0]["nodeId"] = "node-2"
    save(db, other, "r2", [item2])
    another_workspace, item3 = fixture()
    another_workspace.update(executionId="exec-3", workspace="accepted")
    item3["execution"].update(executionId="exec-3", workspace="accepted")
    save(db, another_workspace, "r3", [item3])
    assert len(read(db, record["project"], record["workspace"])["cohorts"]) == 1
    assert read(db, record["project"], record["workspace"], node="missing")["cohorts"] == []
    assert read(db, record["project"], record["workspace"], resource="other")["cohorts"] == []
    bad = copy.deepcopy(item)
    bad["resource"]["digest"] = "0" * 64
    save(db, record, "r3", [bad])
    report = read(db, record["project"], record["workspace"])
    assert report["invalidReceipts"] == 1
    assert report["cohorts"][0]["invocations"] == 1


def test_limit_is_explicit_and_truncates_newest_receipt_window():
    db = database()
    record, first = fixture()
    save(db, record, "r1", [first])
    second = copy.deepcopy(first)
    second["invocationId"] = str(uuid.uuid4())
    second["durationMs"] = 30
    save(db, record, "r2", [second])
    report = read(db, record["project"], record["workspace"], limit=1)
    assert report["limited"] is True and report["receiptWindowLimited"] is True
    assert report["scannedReceipts"] == 1
    assert report["cohorts"][0]["invocations"] == 1

