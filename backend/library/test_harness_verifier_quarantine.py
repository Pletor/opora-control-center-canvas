"""Real SQLite history proves old native failures cannot age out of quarantine."""
import uuid

import pytest

from backend.canvas.opora_verifications import OporaVerifications
from backend.canvas.test_opora_changesets import (
    service as service,  # noqa: PLC0414 - explicit pytest fixture re-export.
)
from backend.library.harness_verifier_quarantine import read
from database.repositories.opora_verifications import Verifications


def record(problem="problem:one", fingerprint="a" * 64, outcome="failed"):
    identifier = uuid.uuid4().hex
    return {"id": identifier, "project": "draft", "workspace": "draft", "nodeId": "a",
            "executionId": "exec-" + identifier, "requestId": "request-" + identifier,
            "requestDigest": "b" * 64, "verification": {"artifacts": []}, "domain": "harness-fixtures", "trust": "server-pending",
            "sourceBinding": "canvas-verified", "currentEligibility": False,
            "origin": {"kind": "harness-server-verifier", "protocol": "harness.server-fixtures/1",
                       "problem": problem, "candidate": {"id": "scripts:tool", "digest": fingerprint}}}, {
            "requestId": "report-" + identifier, "artifacts": [], "reportDigest": "c" * 64, "trust": "server-observed",
            "sourceBinding": "canvas-verified", "currentEligibility": False, "promotionAllowed": False,
            "independentlyVerified": True, "authorityCurrentAtCompletion": True, "outcome": outcome,
            "paired": {"complete": True, "cleanupComplete": True}}


def insert(canvas, records, workspace="draft"):
    with OporaVerifications(canvas).transaction("draft", workspace) as repo:
        store = Verifications(repo.db, "draft", workspace)
        for request, report in records:
            store.insert(request)
            if report is not None:
                store.insert_report(request["id"], report)


def test_old_failure_survives_recent_passes_and_duplicate_failure_groups(service):
    first = record()
    insert(service, [first, record()] + [record(outcome="passed") for _ in range(101)])
    recent = OporaVerifications(service).history("draft", "draft", domain="harness-fixtures")["requests"]
    assert len(recent) == 100 and all(item["report"]["outcome"] == "passed" for item in recent)
    result = read(service, "draft", "draft")
    assert result["complete"] and result["unboundFailures"] == 0
    assert result["scope"] == {"project": "draft", "workspace": "draft"}
    assert result["schema"] == "harness.fixture-quarantine/1"
    assert len(result["cohorts"]) == 1
    assert result["cohorts"][0]["candidate"] == {"id": "scripts:tool", "digest": "a" * 64}


def test_exact_problem_version_and_workspace_are_separate(service):
    insert(service, [record(), record(fingerprint="d" * 64), record(problem="problem:other")])
    foreign = record(problem="problem:foreign")
    foreign[0]["workspace"] = "another"
    insert(service, [foreign], workspace="another")
    assert len(read(service, "draft", "draft")["cohorts"]) == 3
    assert [c["problem"] for c in read(service, "draft", "another")["cohorts"]] == ["problem:foreign"]
    assert read(service, "draft", "empty")["cohorts"] == []
    with pytest.raises(ValueError):
        read(service, "draft", "../escape")


@pytest.mark.parametrize("path,value", [
    (("request", "trust"), "agent-reported"),
    (("request", "domain"), "formal"),
    (("request", "origin", "kind"), "worker"),
    (("request", "origin", "protocol"), "harness.server-fixtures/0"),
    (("report", "trust"), "agent-reported"),
    (("request", "sourceBinding"), "agent-reported"),
    (("report", "sourceBinding"), "agent-reported"),
    (("report", "currentEligibility"), True),
    (("report", "promotionAllowed"), True),
    (("report", "independentlyVerified"), False),
    (("report", "independentlyVerified"), 1),
    (("report", "authorityCurrentAtCompletion"), False),
    (("report", "paired", "complete"), False),
    (("report", "paired", "cleanupComplete"), False),
    (("report", "outcome"), "inconclusive"),
])
def test_worker_stale_incomplete_or_wrong_domain_never_quarantines(service, path, value):
    request, report = record()
    root = {"request": request, "report": report}
    target = root
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    insert(service, [(request, report), (record()[0], None)])
    result = read(service, "draft", "draft")
    assert result["complete"] and result["cohorts"] == [] and result["unboundFailures"] == 0


def test_qualifying_missing_or_malformed_binding_is_explicit_unknown(service):
    records = [record(problem=None), record(problem=""), record(problem="bad\nproblem"), record(fingerprint="bad"), record(problem="problem:one\0suffix")]
    missing = record()
    del missing[0]["origin"]["problem"]
    insert(service, records + [missing, record()])
    result = read(service, "draft", "draft")
    assert not result["complete"] and result["unboundFailures"] == 6
    assert len(result["cohorts"]) == 1


def test_overflow_is_explicit_and_new_pass_cannot_clear(service):
    insert(service, [record(problem=f"problem:{index:04}") for index in range(1001)])
    result = read(service, "draft", "draft")
    assert not result["complete"] and result["unboundFailures"] == 0
    assert len(result["cohorts"]) == 1000
    insert(service, [record(problem="problem:0000", outcome="passed")])
    assert read(service, "draft", "draft") == result


def test_report_join_cannot_cross_workspace(service):
    request, report = record()
    insert(service, [(request, None)])
    with OporaVerifications(service).transaction("draft", "foreign") as repo:
        Verifications(repo.db, "draft", "foreign").insert_report(request["id"], report)
    assert read(service, "draft", "draft")["cohorts"] == []


def test_other_project_rows_in_same_database_do_not_leak(service):
    request, report = record(problem="problem:foreign-project")
    with OporaVerifications(service).transaction("draft", "draft") as repo:
        foreign = Verifications(repo.db, "foreign-project", "draft")
        foreign.insert(request)
        foreign.insert_report(request["id"], report)
        assert foreign.read(request["id"])["report"]["outcome"] == "failed"
    assert read(service, "draft", "draft")["cohorts"] == []
