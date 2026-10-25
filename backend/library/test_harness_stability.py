"""Eligibility from isolated native-shaped facts; not production acceptance or promotion."""
import hashlib
import json

import pytest

from backend.canvas.graph import digest
from backend.library import harness_stability as stability
from backend.library import harness_verifier as verifier_module
from backend.library import harness_verifier_records as records
from backend.library.test_harness_exploration import baseline, projection
from backend.library.test_harness_verifier import authority as authority  # noqa: PLC0414
from backend.library.test_harness_verifier import fixture_plan, observed, payload
from backend.library.test_harness_verifier import service as service  # noqa: PLC0414
from backend.library.test_harness_verifier import setup as setup  # noqa: PLC0414

RESOURCE = {"resource": "script:candidate", "category": "scripts", "digest": "d" * 64,
            "requires": ["command:node"]}


def seed(db, count=20, start=1):
    projection(db)
    db.executescript("""
      CREATE TABLE IF NOT EXISTS harness_learning_resources(project_id,workspace_id,execution_id,
        resource_id,content_digest,version_digest,category);
      CREATE TABLE IF NOT EXISTS harness_learning_problems(project_id,workspace_id,execution_id,problem);
    """)
    with db:
        for index in range(start, count + 1):
            baseline(db, index)
            db.execute("INSERT INTO harness_learning_resources VALUES(?,?,?,?,?,?,?)",
                       ("draft", "draft", f"baseline-{index}", RESOURCE["resource"], RESOURCE["digest"],
                        digest(RESOURCE), RESOURCE["category"]))
            db.execute("INSERT INTO harness_learning_problems VALUES(?,?,?,?)",
                       ("draft", "draft", f"baseline-{index}", "evaluation:paired-node"))


@pytest.fixture
def prepared(setup, monkeypatch):
    verifier, canvas, _, record, _, _ = setup
    monkeypatch.setenv("OPORA_HARNESS_STABILITY", json.dumps({"project": "draft", "workspace": "draft",
                      "approvedPlanDigests": ["b" * 64]}))
    # Existing setup isolates accepted-plan resolution and container execution. These tests
    # exercise the native assessment with real SQLite records and an explicitly mocked runner.
    monkeypatch.setattr(stability, "candidate_resource", lambda *args: dict(RESOURCE))
    monkeypatch.setattr(stability, "regression_evidence", lambda *args: {"affectedExecutions": 0})
    def runner(*args):
        result = observed()
        for trial in result["trials"]:
            trial["outputDigest"] = hashlib.sha256(b"1").hexdigest()
        return result
    monkeypatch.setattr(verifier_module, "run_paired_fixture", runner)
    report = verifier.verify(payload(record))
    db = canvas.db_for("draft")
    seed(db)
    return stability.HarnessStability(canvas), db, record, report


def test_assessment_reports_exact_evidence_without_mutating_stable_state(prepared):
    assess, db, record, report = prepared
    before = db.total_changes
    result = assess.assess(payload(record))
    assert result["eligible"] is True and result["reasons"] == []
    assert result["promotionAllowed"] is False and result["reservation"] is False
    assert result["cohort"]["verifiedPasses"] == 20 and result["cohort"]["verifiedCards"] == 20
    assert result["comparison"]["reports"] == [{"verificationId": report["id"], "reportDigest": report["report"]["reportDigest"]}]
    assert result["evidenceDigest"] == digest({k: v for k, v in result.items() if k != "evidenceDigest"})
    assert record["token"] not in json.dumps(result)
    assert db.total_changes == before


@pytest.mark.parametrize("change", ["reported", "foreign-event", "external-event", "pruned", "reopened", "unmerged", "version", "problem"])
def test_unverified_or_incompatible_rows_never_supply_success_credit(prepared, change):
    assess, db, record, _ = prepared
    with db:
        if change == "reported": db.execute("UPDATE harness_learning_outcomes SET tier='reported'")
        elif change == "foreign-event": db.execute("UPDATE opora_events SET node_id='other' WHERE kind='decision.resolved'")
        elif change == "external-event": db.execute("UPDATE opora_events SET source='external' WHERE kind='decision.resolved'")
        elif change == "pruned": db.execute("DELETE FROM opora_events WHERE kind='decision.resolved'")
        elif change == "reopened": db.execute("UPDATE desktop_v3_state SET state=json_set(state,'$.nodes',json('{}'))")
        elif change == "unmerged": db.execute("UPDATE opora_execution_pull_requests SET state='open'")
        elif change == "version": db.execute("UPDATE harness_learning_resources SET version_digest=?", ("e" * 64,))
        else: db.execute("UPDATE harness_learning_problems SET problem='different'")
    result = assess.assess(payload(record))
    assert result["eligible"] is False and result["cohort"]["verifiedPasses"] == 0


def test_unknown_outcomes_remain_in_coverage_and_reopening_changes_fingerprint(prepared):
    assess, db, record, _ = prepared
    original = assess.assess(payload(record))
    with db:
        db.execute("UPDATE harness_learning_outcomes SET outcome='unknown' WHERE execution_id IN ('baseline-1','baseline-2')")
    result = assess.assess(payload(record))
    assert result["cohort"]["executions"] == 20 and result["cohort"]["unknown"] == 2
    assert result["cohort"]["coverage"] == .9 and "insufficient-evidence-coverage" in result["reasons"]
    assert result["evidenceDigest"] != original["evidenceDigest"]


@pytest.mark.parametrize("change", ["output", "baseline", "reason", "cleanup", "complete", "exit"])
def test_rehashed_but_contradictory_observations_are_rejected(prepared, change):
    assess, db, record, report = prepared
    request = json.loads(db.execute("SELECT record FROM opora_verification_requests WHERE id=?", (report["id"],)).fetchone()[0])
    paired = report["report"]["paired"]
    if change == "output": paired["trials"][1]["outputDigest"] = "f" * 64
    elif change == "baseline":
        paired["trials"][0]["outcome"] = "fail"
        paired["improvements"] = 1
    elif change == "reason": paired["trials"][0]["reason"] = "nonzero-exit"
    elif change == "cleanup": paired["cleanupComplete"] = "yes"
    elif change == "complete": paired["complete"] = 1
    else: paired["trials"][0]["exitCode"] = False
    with db:
        db.execute("UPDATE opora_verification_reports SET record=? WHERE verification_id=?",
                   (json.dumps(records.report(request, paired, True)), report["id"]))
    result = assess.assess(payload(record))
    assert result["eligible"] is False
    assert result["comparison"]["complete"] is False


@pytest.mark.parametrize("change", ["unapproved-plan", "regression", "missing-regressions", "missing-learning", "bad-report", "pending"])
def test_each_gate_fails_closed(prepared, monkeypatch, change):
    assess, db, record, report = prepared
    if change == "unapproved-plan":
        monkeypatch.setenv("OPORA_HARNESS_STABILITY", json.dumps({"project": "draft", "workspace": "draft", "approvedPlanDigests": ["e" * 64]}))
    elif change == "regression": monkeypatch.setattr(stability, "regression_evidence", lambda *args: {"affectedExecutions": 1})
    elif change == "missing-regressions": monkeypatch.setattr(stability, "regression_evidence", lambda *args: None)
    elif change == "missing-learning":
        with db: db.execute("DROP TABLE harness_learning_resources")
    elif change == "pending":
        with db: db.execute("DELETE FROM opora_verification_reports WHERE verification_id=?", (report["id"],))
    else:
        with db: db.execute("UPDATE opora_verification_reports SET record=json_set(record,'$.reportDigest',?)", ("0" * 64,))
    result = assess.assess(payload(record))
    assert result["eligible"] is False and result["reasons"]


def test_policy_scope_strictness_and_authority(prepared, monkeypatch):
    assess, _, record, _ = prepared
    for value in [{}, {"project": "foreign", "workspace": "draft", "approvedPlanDigests": ["b" * 64]},
                  {"project": "draft", "workspace": "draft", "approvedPlanDigests": ["b" * 64 + "\n"]},
                  {"project": "draft", "workspace": "draft", "approvedPlanDigests": ["b" * 64], "minimumVerifiedOutcomes": 1}]:
        monkeypatch.setenv("OPORA_HARNESS_STABILITY", json.dumps(value))
        with pytest.raises(ValueError): assess.assess(payload(record))
    monkeypatch.setenv("OPORA_HARNESS_STABILITY", json.dumps({"project": "draft", "workspace": "draft", "approvedPlanDigests": ["b" * 64]}))
    with pytest.raises(ValueError): assess.assess(payload(record, token="0" * 64))
    with pytest.raises(ValueError): assess.assess({**payload(record), "verified": True})


def test_accepted_candidate_requires_exact_target_and_supported_requirements():
    record = {"nodeId": "card", "assignment": {"documents": [{"nodeId": "card", "fields": {"harness": {"resources": [RESOURCE]}}}]}}
    assert stability.candidate_resource(record, fixture_plan()) == RESOURCE
    record["nodeId"] = "neighbor"
    with pytest.raises(ValueError): stability.candidate_resource(record, fixture_plan())


def test_http_assessment_uses_existing_actor_body_and_lease_boundaries(prepared):
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient

    from backend.api.editor.harness_verifier_routes import create_harness_verifier_router
    assess, _, record, _ = prepared
    app = FastAPI()
    @app.middleware("http")
    async def actor(request: Request, next_call):
        request.state.actor = request.headers.get("x-fixture-actor", "anonymous")
        return await next_call(request)
    app.include_router(create_harness_verifier_router(assess.canvas))
    with TestClient(app) as client:
        url = "/api/oporahub/harness-verifier/eligibility"
        assert client.post(url, json=payload(record)).status_code == 428
        headers = {"x-fixture-actor": "agent"}
        assert client.post(url, content=b" " * 4097, headers=headers).status_code == 413
        assert client.post(url, json=payload(record, token="0" * 64), headers=headers).status_code == 409
        response = client.post(url, json=payload(record), headers=headers)
        assert response.status_code == 200 and response.json()["eligible"] is True
        assert record["token"] not in response.text
