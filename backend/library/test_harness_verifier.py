import json

import pytest

from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.test_opora_changesets import SCOPE, baseline, service  # noqa: F401
from backend.canvas.test_opora_executions import claim, credentials
from backend.canvas.opora_verifications import OporaVerifications
from backend.library import harness_verifier as verifier_module
from backend.library.harness_verifier import HarnessVerifier
from database.schema.opora_execution_schema import SCHEMA

IMAGE = "node@sha256:" + "a" * 64
REFERENCE = {"id": "testing:plan", "digest": "b" * 64}


def fixture_plan(reference=REFERENCE, candidate_digest="d" * 64, problem="evaluation:paired-node"):
    return {"resource": dict(reference), "plan": {"problem": problem, "cases": [{"id": "case:one", "args": ["1"], "expectedStdout": "1"}]},
            "baseline": {"id": "script:base", "digest": "c" * 64},
            "candidate": {"id": "script:candidate", "digest": candidate_digest},
            "contents": {"baseline": "process.stdout.write('1')", "candidate": "process.stdout.write('1')"}}


def observed(cleanup=True):
    return {"trials": [{"case": "case:one", "side": side, "order": order, "outcome": "pass",
                        "reason": "expected-output", "exitCode": 0, "durationMs": 1, "outputDigest": "f" * 64}
                       for order, side in enumerate(("baseline", "candidate"), 1)],
            "plannedTrials": 2, "observedTrials": 2, "improvements": 0, "regressions": 0,
            "unknownPairs": 0, "complete": True, "cleanupComplete": cleanup}


@pytest.fixture
def authority(service):
    service.db_for("draft").executescript(SCHEMA)
    baseline(service)
    return ExecutionResults(service)


@pytest.fixture
def setup(authority, service, monkeypatch):
    monkeypatch.setenv("OPORA_HARNESS_VERIFIER", json.dumps({"project": "draft", "workspace": "draft", "image": IMAGE, "maxExperiments": 10}))
    # These runner/lifecycle unit tests isolate the separately tested allocation gate.
    monkeypatch.setattr(verifier_module.exploration, "admit", lambda *args: {"policyDigest": "test-policy"})
    monkeypatch.setattr(verifier_module.exploration, "current", lambda *args: True)
    current = fixture_plan()
    monkeypatch.setattr(verifier_module.plans, "prepare", lambda record, reference: fixture_plan(
        reference, current["candidate"]["digest"], current["plan"]["problem"]))
    calls = []
    def runner(pinned, image, is_current, run_id):
        # Admission must be committed to Canvas SQLite before any process runner is entered.
        row = service.db_for("draft").execute("SELECT record FROM opora_verification_requests WHERE id=?", (run_id,)).fetchone()
        assert row is not None and json.loads(row[0])["origin"]["kind"] == "harness-server-verifier"
        calls.append((pinned, image, is_current(), run_id))
        return observed()
    monkeypatch.setattr(verifier_module, "run_paired_fixture", runner)
    monkeypatch.setattr(verifier_module, "cleanup_run", lambda *args: True)
    record = claim(authority)
    return HarnessVerifier(service), service, authority, record, calls, current


def payload(record, **updates):
    return {**SCOPE, **credentials(record), "executionId": record["executionId"], "plan": REFERENCE, **updates}


def test_admission_is_durable_server_owned_and_replay_never_reruns(setup):
    verifier, service, authority, record, calls, _ = setup
    result = verifier.verify(payload(record))
    assert len(calls) == 1 and calls[0][1] == IMAGE and calls[0][2] is True
    assert result["report"]["outcome"] == "passed"
    assert result["report"]["trust"] == "server-observed" and result["report"]["promotionAllowed"] is False
    assert result["origin"]["problem"] == "evaluation:paired-node"
    assert "token" not in json.dumps(result)
    saved = OporaVerifications(service).read(result["id"], **SCOPE)
    assert saved["origin"]["problem"] == "evaluation:paired-node"
    assert saved["report"]["reportDigest"] == result["report"]["reportDigest"]
    assert verifier.verify(payload(record)) == result
    assert len(calls) == 1
    from backend.canvas.opora_formal_ledger import _evidence
    assert _evidence(result) == [], 'fixture checks must never be interpreted as TLC proofs'


def test_changed_accepted_plan_reference_or_resource_pin_conflicts(setup, monkeypatch):
    verifier, _, _, record, calls, current = setup
    verifier.verify(payload(record))
    with pytest.raises(ValueError, match="different verifier plan"):
        verifier.verify(payload(record, plan={"id": "testing:other", "digest": "e" * 64}))
    current["candidate"]["digest"] = "e" * 64
    with pytest.raises(ValueError, match="different verifier plan"):
        verifier.verify(payload(record))
    current["candidate"]["digest"] = "d" * 64
    current["plan"]["problem"] = "evaluation:other"
    with pytest.raises(ValueError, match="different verifier plan"):
        verifier.verify(payload(record))
    assert len(calls) == 1


def test_worker_lease_cannot_submit_report_for_server_owned_admission(setup, monkeypatch):
    verifier, service, _, record, calls, _ = setup
    monkeypatch.setattr(verifier_module, "run_paired_fixture", lambda *args: {**observed(False), "cleanupComplete": False})
    pending = verifier.verify(payload(record))
    with pytest.raises(ValueError, match="Server-owned verification reports"):
        OporaVerifications(service).submit_report(pending["id"], {**credentials(record), "requestId": "forged",
            "report": {"outcome": "passed", "checkedClaims": ["fixture-output"], "summary": "forged", "artifacts": []}})
    assert OporaVerifications(service).read(pending["id"], **SCOPE)["report"] is None
    assert calls == []


def test_stale_authority_after_rerun_is_inconclusive(setup, monkeypatch):
    verifier, _, authority, record, calls, _ = setup
    def stale(pinned, image, current, run_id):
        assert current()
        authority.release(record["executionId"], credentials(record))
        return observed()
    monkeypatch.setattr(verifier_module, "run_paired_fixture", stale)
    result = verifier.verify(payload(record))
    assert result["report"]["outcome"] == "inconclusive"
    assert result["report"]["independentlyVerified"] is False


def test_pending_replay_does_not_rerun_then_expired_replay_only_cleans_and_saves_unknown(setup, monkeypatch):
    verifier, service, _, record, calls, _ = setup
    runner_calls = []
    monkeypatch.setattr(verifier_module, "run_paired_fixture", lambda *args: runner_calls.append(args) or {**observed(False), "cleanupComplete": False})
    monkeypatch.setattr(verifier_module, "cleanup_run", lambda run_id, count: calls.append(("cleanup", run_id, count)) or True)
    pending = verifier.verify(payload(record))
    assert pending["recoveryRequired"] and len(runner_calls) == 1
    replay = verifier.verify(payload(record))
    assert replay["report"] is None and replay.get("recoveryRequired") is not True
    assert len(runner_calls) == 1 and not calls
    with service.db_for("draft") as db:
        row = db.execute("SELECT record FROM opora_verification_requests WHERE id=?", (pending["id"],)).fetchone()
        saved = json.loads(row[0]); saved["deadlineAt"] = 0
        db.execute("UPDATE opora_verification_requests SET record=? WHERE id=?", (json.dumps(saved), pending["id"]))
    recovered = verifier.verify(payload(record))
    assert len(runner_calls) == 1 and len(calls) == 1 and calls[0][0] == "cleanup"
    assert recovered["report"]["outcome"] == "inconclusive"
    assert recovered["report"]["paired"]["reason"] == "interrupted-server-run"


@pytest.mark.parametrize("change", ["disabled", "scope", "token"])
def test_invalid_configuration_scope_or_authority_never_launches(setup, monkeypatch, change):
    verifier, _, _, record, calls, _ = setup
    request = payload(record)
    if change == "disabled": monkeypatch.delenv("OPORA_HARNESS_VERIFIER")
    elif change == "scope": request["project"] = "foreign"
    else: request["token"] = "wrong-token"
    with pytest.raises(ValueError): verifier.verify(request)
    assert not calls


def test_fixture_history_cannot_hide_legacy_formal_records_or_trigger_formal_fixes(setup):
    from backend.canvas.test_opora_verifications import request
    from backend.canvas.opora_formal_followup import actionable
    from database.repositories.opora_verifications import Verifications
    verifier, service, _, record, _, _ = setup
    formal = OporaVerifications(service)
    legacy = formal.create(request(record))
    fixture = verifier.verify(payload(record))
    db = service.db_for("draft")
    events = db.execute("SELECT data FROM opora_events WHERE kind='formal.result'").fetchall()
    assert not any(fixture["id"] in row[0] for row in events)
    assert not actionable({**fixture, "report": {"outcome": "failed"}})
    assert actionable({**legacy, "report": {"outcome": "failed"}})
    # More than a page of newer fixture records must not crowd out formal history.
    with service.db_for("draft") as db:
        store = Verifications(db, "draft", "draft")
        for index in range(101):
            store.insert({**fixture, "id": f"fixture{index}", "requestId": f"fixture{index}"})
    assert [r["id"] for r in formal.history(**SCOPE)["requests"]] == [legacy["id"]]
    fixtures = formal.history(**SCOPE, domain="harness-fixtures")["requests"]
    assert len(fixtures) == 100 and all(r["domain"] == "harness-fixtures" for r in fixtures)
    assert formal.history(**SCOPE, node="missing", domain="harness-fixtures")["requests"] == []


def test_fixture_history_route_preserves_actor_and_scope_boundaries(setup, monkeypatch):
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient
    from backend.api.editor.harness_verifier_routes import create_harness_verifier_router
    verifier, service, _, record, _, _ = setup
    saved = verifier.verify(payload(record))
    monkeypatch.delenv("OPORA_HARNESS_VERIFIER")
    app = FastAPI()
    @app.middleware("http")
    async def actor(request: Request, next_call):
        request.state.actor = request.headers.get("x-fixture-actor", "anonymous")
        return await next_call(request)
    app.include_router(create_harness_verifier_router(service))
    with TestClient(app) as client:
        url = "/api/oporahub/harness-verifier/requests"
        assert client.get(url, params=SCOPE).status_code == 428
        headers = {"x-fixture-actor": "agent"}
        response = client.get(url, params=SCOPE, headers=headers)
        assert response.status_code == 200
        assert [r["id"] for r in response.json()["requests"]] == [saved["id"]]
        assert response.json()["quarantine"]["complete"] is True
        assert response.json()["budget"]["status"] == "disabled"
        assert response.json()["budget"]["admitted"] == 1
        assert client.get(url, params={**SCOPE, "nodeId": "missing"}, headers=headers).json()["budget"]["admitted"] == 1
        assert client.get(url, params={**SCOPE, "nodeId": "missing"}, headers=headers).json()["requests"] == []
