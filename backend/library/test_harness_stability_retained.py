"""Retained proof is rechecked after lease release; it never revives execution authority."""
import json

import pytest

from backend.canvas.graph import digest
from backend.library import harness_stability as stability
from backend.library.harness_stability_retained import RetainedStability
from backend.library.test_harness_stability import prepared as prepared  # noqa: PLC0414
from backend.library.test_harness_verifier import authority as authority  # noqa: PLC0414
from backend.library.test_harness_verifier import payload
from backend.library.test_harness_verifier import service as service  # noqa: PLC0414
from backend.library.test_harness_verifier import setup as setup  # noqa: PLC0414


def reference(report):
    return {"project": report["project"], "workspace": report["workspace"], "verificationId": report["id"]}


def test_released_source_reassesses_without_execution_authority_or_mutation(prepared):
    live, db, record, report = prepared
    live.release(record["executionId"], {k: record[k] for k in ("project", "workspace", "token", "epoch")})
    with pytest.raises(ValueError):
        live.assess(payload(record))
    before = db.total_changes
    result = RetainedStability(live.canvas).assess(reference(report))
    assert result["eligible"] is True and result["executionAuthority"] is False
    assert result["schema"] == "harness.retained-stability/1"
    assert result["source"] == {"kind": "retained-native-verification", "verificationId": report["id"],
                                "requestDigest": report["requestDigest"], "reportDigest": report["report"]["reportDigest"]}
    assert result["promotionAllowed"] is False and result["reservation"] is False
    assert result["evidenceDigest"] == digest({k: v for k, v in result.items() if k != "evidenceDigest"})
    assert record["token"] not in json.dumps(result) and "assignment" not in result
    assert db.total_changes == before


@pytest.mark.parametrize("change", ["policy", "regression", "pending", "bad-report", "missing-learning"])
def test_retained_assessment_uses_current_evidence_not_old_positive_label(prepared, monkeypatch, change):
    live, db, _, report = prepared
    reader = RetainedStability(live.canvas)
    assert reader.assess(reference(report))["eligible"]
    if change == "policy":
        monkeypatch.setenv("OPORA_HARNESS_STABILITY", json.dumps({"project": "draft", "workspace": "draft", "approvedPlanDigests": ["e" * 64]}))
    elif change == "regression":
        monkeypatch.setattr(stability, "regression_evidence", lambda *args: {"affectedExecutions": 1})
    elif change == "missing-learning":
        with db: db.execute("DROP TABLE harness_learning_resources")
    elif change == "pending":
        with db: db.execute("DELETE FROM opora_verification_reports WHERE verification_id=?", (report["id"],))
    else:
        with db: db.execute("UPDATE opora_verification_reports SET record=json_set(record,'$.reportDigest',?)", ("0" * 64,))
    result = reader.assess(reference(report))
    assert result["eligible"] is False and result["reasons"]


@pytest.mark.parametrize("field,value", [("trust", "agent-reported"), ("epoch", 99),
    ("origin.kind", "worker-import"), ("origin.candidate.digest", "e" * 64), ("requestDigest", "0" * 64)])
def test_retained_source_binding_rejects_tampered_native_request(prepared, field, value):
    live, db, _, report = prepared
    with db:
        db.execute("UPDATE opora_verification_requests SET record=json_set(record,?,?) WHERE id=?",
                   ("$." + field, value, report["id"]))
    with pytest.raises(ValueError):
        RetainedStability(live.canvas).assess(reference(report))


def test_retained_scope_input_and_assignment_are_not_caller_assertions(prepared):
    live, db, record, report = prepared
    reader = RetainedStability(live.canvas)
    for extra in ({"workspace": "foreign"}, {"eligible": True}, {"token": record["token"]}, {"verificationId": "absent"}):
        with pytest.raises(ValueError):
            reader.assess({**reference(report), **extra})
    with db:
        db.execute("UPDATE opora_executions SET record=json_set(record,'$.assignmentDigest',?) WHERE id=?",
                   ("0" * 64, record["executionId"]))
    with pytest.raises(ValueError):
        reader.assess(reference(report))


def test_retained_http_actor_and_bounded_body(prepared):
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient

    from backend.api.editor.harness_verifier_routes import create_harness_verifier_router

    live, _, record, report = prepared
    app = FastAPI()
    @app.middleware("http")
    async def actor(request: Request, next_call):
        request.state.actor = request.headers.get("x-fixture-actor", "anonymous")
        return await next_call(request)
    app.include_router(create_harness_verifier_router(live.canvas))
    with TestClient(app) as client:
        url = "/api/oporahub/harness-verifier/eligibility/retained"
        assert client.post(url, json=reference(report)).status_code == 428
        headers = {"x-fixture-actor": "agent"}
        assert client.post(url, content=b" " * 4097, headers=headers).status_code == 413
        assert client.post(url, json={**reference(report), "eligible": True}, headers=headers).status_code == 409
        response = client.post(url, json=reference(report), headers=headers)
        assert response.status_code == 200 and response.json()["eligible"] is True
        assert response.json()["executionAuthority"] is False and record["token"] not in response.text
