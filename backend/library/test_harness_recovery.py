"""Recovery uses real accepted kits and live execution authority, never a file archive."""
import copy
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.editor.harness_learning_routes import create_harness_learning_router
from backend.canvas.graph import digest
from backend.canvas.test_opora_changesets import accept
from backend.canvas.test_opora_execution_context import claimed
from backend.library.harness_kit import kit_of_assignment
from backend.library.harness_recovery import HarnessRecovery
from backend.library.test_harness_kit import kit, propose_kit
from database.repositories.opora_executions import Executions


@pytest.fixture
def recovery(learning_plan):
    graphs, authority, _ = learning_plan
    old = claimed(learning_plan)
    authority.release(old["executionId"], {"project": "draft", "workspace": "draft",
                      "token": old["token"], "epoch": old["epoch"]})
    proposal, head = propose_kit(learning_plan, kit("New candidate content"), {"steps": old["assignment"]["steps"]})
    accept(graphs.service, proposal, head)
    current = claimed(learning_plan, request="second")
    payload = {"project": "draft", "workspace": "draft", "executionId": current["executionId"],
               "token": current["token"], "epoch": current["epoch"],
               "sourceExecutionId": old["executionId"], "resource": "rule:quality"}
    return graphs.service, authority, old, current, payload


def test_recovery_preserves_bytes_and_running_assignment_without_fake_success(recovery):
    canvas, _, old, current, payload = recovery
    db = canvas.db_for("draft")
    before = db.execute("SELECT record FROM opora_executions ORDER BY id").fetchall()
    result = HarnessRecovery(canvas).preview(payload)
    original = kit_of_assignment(old["assignment"], old["nodeId"])
    assert result["kit"] == original
    assert result["source"]["digest"] == original["resources"][0]["digest"]
    assert result["assignmentDigest"] == current["assignmentDigest"]
    assert result["requiresAcceptance"] is True and result["promotionAllowed"] is False
    assert result["evidence"]["verifiedOutcome"] == "unknown"
    assert "token" not in json.dumps(result)
    assert db.execute("SELECT record FROM opora_executions ORDER BY id").fetchall() == before
    assert HarnessRecovery(canvas).preview(payload) == result


@pytest.mark.parametrize("change", [{"token": "0" * 64}, {"epoch": 999}, {"workspace": "foreign"},
    {"resource": "rule:other"}, {"resource": "../private"}, {"promotionAllowed": True}])
def test_rejects_unauthorized_or_incompatible_requests(recovery, change):
    canvas, _, _, _, payload = recovery
    with pytest.raises(ValueError):
        HarnessRecovery(canvas).preview({**payload, **change})


def test_released_current_execution_cannot_recover(recovery):
    canvas, authority, _, current, payload = recovery
    authority.release(current["executionId"], {key: payload[key] for key in ("project", "workspace", "token", "epoch")})
    with pytest.raises(ValueError):
        HarnessRecovery(canvas).preview(payload)


@pytest.mark.parametrize("mutation", ["card", "epoch", "digest", "category", "requirements", "problem", "identical"])
def test_source_scope_integrity_and_compatibility_are_not_inferred(recovery, mutation):
    canvas, _, old, current, payload = recovery
    altered = copy.deepcopy(old)
    resource = kit_of_assignment(altered["assignment"], altered["nodeId"])["resources"][0]
    if mutation == "card":
        altered["nodeId"] = "other-card"
    elif mutation == "epoch":
        altered["epoch"] = current["epoch"]
    elif mutation == "digest":
        altered["assignmentDigest"] = "0" * 64
    elif mutation == "category":
        resource["category"] = "scripts"
    elif mutation == "requirements":
        resource["requires"] = ["network:unrestricted"]
    elif mutation == "problem":
        kit_of_assignment(altered["assignment"], altered["nodeId"])["problems"] = ["other"]
    else:
        current_resource = kit_of_assignment(current["assignment"], current["nodeId"])["resources"][0]
        resource.update(current_resource)
    if mutation in {"category", "requirements", "problem", "identical"}:
        altered["assignmentDigest"] = digest(altered["assignment"])
    db = canvas.db_for("draft")
    with db:
        Executions(db, "draft", "draft").save(altered)
    with pytest.raises(ValueError):
        HarnessRecovery(canvas).preview(payload)


def test_known_verified_failure_refuses_historical_content(recovery):
    canvas, _, old, _, payload = recovery
    db = canvas.db_for("draft")
    with db:
        db.execute("UPDATE harness_learning_outcomes SET outcome='fail' WHERE execution_id=? AND tier='verified'",
                   (old["executionId"],))
    with pytest.raises(ValueError, match="verified failure"):
        HarnessRecovery(canvas).preview(payload)


def test_registered_route_requires_identity_credential_and_bounded_input(recovery):
    canvas, _, _, _, payload = recovery
    app = FastAPI()
    @app.middleware("http")
    async def actor(request, call_next):
        request.state.actor = request.headers.get("x-test-actor")
        return await call_next(request)
    app.include_router(create_harness_learning_router(canvas))
    with TestClient(app) as client:
        url = "/api/oporahub/harness-recovery"
        assert client.post(url, json=payload).status_code == 428
        headers = {"x-test-actor": "agent"}
        assert client.post(url, json={**payload, "token": "0" * 64}, headers=headers).status_code == 409
        assert client.post(url, content=b"x" * 4097, headers=headers).status_code == 413
        response = client.post(url, json=payload, headers=headers)
        assert response.status_code == 200
        assert response.json()["requiresAcceptance"] is True
        assert client.get(url, headers=headers).status_code == 405


def test_native_incident_association_blocks_recovery(recovery):
    from backend.library.test_harness_guardrails import cases
    from backend.library.test_harness_learning import merged_link
    canvas, authority, old, _, payload = recovery
    world = (canvas, authority, {}, old)
    merged_link(world)
    cases(world)
    with pytest.raises(ValueError, match="incident or revert"):
        HarnessRecovery(canvas).preview(payload)


def test_missing_native_enrollment_cannot_be_recovered(recovery):
    canvas, _, old, _, payload = recovery
    db = canvas.db_for("draft")
    with db:
        db.execute("DELETE FROM harness_learning_runs WHERE execution_id=?", (old["executionId"],))
    with pytest.raises(ValueError, match="native enrollment"):
        HarnessRecovery(canvas).preview(payload)


@pytest.mark.parametrize("binding", ["match", "other-version", "unbound"])
def test_installed_native_quarantine_gates_recovery(recovery, binding):
    fixtures = pytest.importorskip("backend.library.test_harness_verifier_quarantine",
                                  reason="Independent verifier module is not installed in this branch")
    canvas, _, old, _, payload = recovery
    resource = kit_of_assignment(old["assignment"], old["nodeId"])["resources"][0]
    request, report = fixtures.record(problem="ts.references", fingerprint=resource["digest"])
    request["origin"]["candidate"]["id"] = resource["resource"]
    if binding == "other-version":
        request["origin"]["candidate"]["digest"] = "f" * 64
    elif binding == "unbound":
        request["origin"]["problem"] = None
    fixtures.insert(canvas, [(request, report)])
    if binding == "other-version":
        result = HarnessRecovery(canvas).preview(payload)
        assert result["evidence"]["fixtureHistory"] == "no-recorded-failure"
    else:
        with pytest.raises(ValueError, match="fixture quarantine"):
            HarnessRecovery(canvas).preview(payload)
