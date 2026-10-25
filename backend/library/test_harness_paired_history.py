import copy
import json
import sqlite3
from types import SimpleNamespace

import pytest

from backend.library.harness_paired_history import validate_result
from backend.library.test_harness_paired_results import valid_report

SCHEMA = """
CREATE TABLE opora_execution_results (
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, execution_id TEXT NOT NULL,
 request_id TEXT NOT NULL, digest TEXT NOT NULL, record TEXT NOT NULL,
 PRIMARY KEY(execution_id, request_id));
"""


def setup():
    db = sqlite3.connect(":memory:")
    db.executescript(SCHEMA)
    record, result = valid_report()
    return db, record, result, SimpleNamespace(db=db, scope=(record["project"], record["workspace"]))


def insert(db, record, request, result, project=None, workspace=None, execution=None):
    receipt = {"result": result}
    db.execute("INSERT INTO opora_execution_results VALUES(?,?,?,?,?,?)",
        (project or record["project"], workspace or record["workspace"], execution or record["executionId"],
         request, "digest-" + request, json.dumps(receipt)))


def test_same_identity_rejects_changed_valid_evidence():
    db, record, result, repo = setup()
    insert(db, record, "first", result)
    changed = copy.deepcopy(result)
    changed["harnessPairedEvaluation"]["durationMs"] += 1
    with pytest.raises(ValueError, match="already used"):
        validate_result(changed, record, repo)


def test_identical_full_and_projected_replay_is_idempotent():
    db, record, result, repo = setup()
    insert(db, record, "first", result)
    projected = copy.deepcopy(result)
    projected["harnessPairedEvaluation"].pop("harnessInvocations")
    assert validate_result(projected, record, repo) is None


@pytest.mark.parametrize("field,value", [("project", "foreign"), ("workspace", "foreign"), ("execution", "other-execution")])
def test_history_isolated_by_project_workspace_and_execution(field, value):
    db, record, result, repo = setup()
    changed = copy.deepcopy(result)
    changed["harnessPairedEvaluation"]["durationMs"] += 1
    kwargs = {"project": None, "workspace": None, "execution": None}
    if field == "project": kwargs["project"] = value
    elif field == "workspace": kwargs["workspace"] = value
    else: kwargs["execution"] = value
    insert(db, record, "foreign", changed, **kwargs)
    assert validate_result(result, record, repo) is None


def test_receipt_scan_bound_and_invalid_history_behavior():
    db, record, result, repo = setup()
    invalid = {"harnessPairedEvaluation": {"evaluationId": "not-valid"}}
    insert(db, record, "invalid", invalid)
    assert validate_result(result, record, repo) is None
    for i in range(128):
        insert(db, record, f"history-{i}", invalid)
    with pytest.raises(ValueError, match="receipt limit"):
        validate_result(result, record, repo)


def test_invalid_historical_claim_is_ignored_but_valid_conflict_is_not():
    db, record, result, repo = setup()
    db.execute("INSERT INTO opora_execution_results VALUES(?,?,?,?,?,?)",
        (record["project"], record["workspace"], record["executionId"], "invalid", "x",
         json.dumps({"result": {"harnessPairedEvaluation": {"evaluationId": "not-a-valid-claim"}}})))
    assert validate_result(result, record, repo) is None
    conflicting = copy.deepcopy(result)
    conflicting["harnessPairedEvaluation"]["durationMs"] += 10
    insert(db, record, "valid-conflict", conflicting)
    with pytest.raises(ValueError, match="already used"):
        validate_result(result, record, repo)
