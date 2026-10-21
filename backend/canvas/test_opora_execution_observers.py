"""Real Canvas claims and actual app HTTP; no provider or paid tool calls."""
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from backend.api.editor.test_opora_changeset_routes import AGENT
from backend.app.factory import create_app
from backend.canvas.opora_execution_budgets import ExecutionBudgets
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.test_canvas_plan import ORIGIN
from backend.canvas.test_opora_changesets import HUMAN, SCOPE
from backend.canvas.test_opora_execution_context import claimed
from backend.canvas.test_opora_execution_context import sparse as sparse  # noqa: PLC0414
from backend.canvas.test_opora_graph_initial import empty_graphs as empty_graphs  # noqa: PLC0414

BASE = "/api/oporahub/execution-observers"
SECRET = "test-only-observer-secret-" + "x" * 32
CONFIG = {**SCOPE, "secret": SECRET, "provider": "anthropic-managed-agents", "maxListCostCents": "1000"}


def signed(raw, stamp=None, **extra):
    stamp = str(int(time.time()) if stamp is None else stamp)
    signature = hmac.new(SECRET.encode(), (stamp + "\n" + hashlib.sha256(raw).hexdigest()).encode(), hashlib.sha256).hexdigest()
    return {"Origin": ORIGIN, "Content-Type": "application/json", "x-opora-observer-id": "broker",
            "x-opora-observer-time": stamp, "x-opora-observer-signature": signature, **extra}


def post(client, path, payload, **headers):
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return client.post(BASE + path, content=raw, headers=signed(raw, **headers))


@pytest.fixture
def broker(sparse, monkeypatch):
    graphs, _, refs = sparse
    monkeypatch.setenv("OPORA_EXECUTION_OBSERVERS", json.dumps({"broker": CONFIG}))
    app = create_app(graphs.service.root)
    authority = ExecutionResults(app.state.service)
    accepted = authority.context(**SCOPE, node=refs["a"])["acceptedHead"]
    policy = ExecutionBudgets(app.state.service).configure({**SCOPE, "nodeId": refs["a"], "expectedPolicyHead": None,
        "expectedAcceptedHead": accepted, "requestId": "policy", "limits": {
            "maxRunSeconds": 60, "maxAttempts": 3, "maxRepairRounds": 1}}, HUMAN)
    lease = claimed((graphs, authority, refs), expectedBudgetPolicyHead=policy["policyHead"], previousExecutionId=None)
    body = {**SCOPE, **{key: lease[key] for key in ("executionId", "nodeId", "epoch", "acceptedRevision", "assignmentDigest", "budget")},
            "requestId": "intent-one", "contextProtocolVersion": 2, "contextVersion": lease["assignment"]["contextVersion"],
            "executionProtocolVersion": 2, "authorityDeadlineAt": lease["budget"]["runDeadlineAt"],
            "provider": CONFIG["provider"], "repository": {"url": "https://github.com/example/repo", "commitSha": "a" * 40},
            "agentId": "agent_one", "agentVersion": 1, "environmentId": "env_one",
            "environmentDigest": "a" * 64, "configurationDigest": "b" * 64, "maxListCostCents": "100"}
    with TestClient(app, base_url=ORIGIN) as client:
        yield client, body, lease


def observation(bound, **changes):
    value = {**SCOPE, "intentId": bound["id"], "requestId": "observed-one", "expectedObservationHead": None,
             "sequence": 1, "sessionId": "session_one", "observedAt": datetime.now(UTC).isoformat(),
             "source": "provider-api", "status": "running", "providerStatus": "running",
             "cumulative": {"inputTokens": 10, "outputTokens": 5, "cacheReadInputTokens": 3,
                            "cacheCreation5mTokens": 2, "cacheCreation1hTokens": 1,
                            "listCostCents": "1", "currency": "USD", "activeSeconds": 342.5}}
    return {**value, **changes}


def test_http_binding_accounting_replay_and_no_capability_leak(broker):
    client, body, lease = broker
    response = post(client, "/intents", body)
    assert response.status_code == 200, response.text
    bound = response.json()
    assert len(bound["id"]) == 40 and bound["authorityActive"]
    assert bound["authorityDeadlineAt"] == lease["budget"]["runDeadlineAt"]
    assert post(client, "/intents", body).json() == bound
    first = observation(bound)
    response = post(client, "/observations", first)
    assert response.status_code == 200, response.text
    recorded = response.json()
    assert recorded["cumulative"]["activeSeconds"] == 342.5
    assert post(client, "/observations", first).json() == recorded
    changed = {**first, "status": "unknown"}
    assert post(client, "/observations", changed).status_code == 409
    summary = client.get(BASE, params=SCOPE, headers=AGENT)
    assert summary.status_code == 200, summary.text
    assert summary.json()["observerConfigured"] and not summary.json()["providerAccessVerified"]
    assert summary.json()["items"][0]["observation"] == recorded
    assert all(secret not in summary.text for secret in (SECRET, lease["token"], '"assignment":', '"pin":'))


@pytest.mark.parametrize("field,value", [("epoch", 999), ("assignmentDigest", "0" * 64),
    ("contextVersion", "0" * 64), ("authorityDeadlineAt", 1), ("executionProtocolVersion", 1),
    ("maxListCostCents", "1001"), ("agentVersion", True), ("workspace", "other")])
def test_wrong_binding_cap_and_scope_reject_without_intent(broker, field, value):
    client, body, _ = broker
    assert post(client, "/intents", {**body, field: value}).status_code in (403, 409)
    assert client.app.state.service.db_for("draft").execute("SELECT COUNT(*) FROM opora_execution_intents").fetchone()[0] == 0


def test_worker_headers_raw_body_tamper_clock_and_origin_cannot_authenticate(broker, monkeypatch):
    client, body, lease = broker
    assert client.post(BASE + "/intents", headers={**AGENT, "X-Opora-Execution-Token": lease["token"]}, json=body).status_code == 403
    raw = json.dumps(body).encode()
    assert client.post(BASE + "/intents", content=raw + b" ", headers=signed(raw)).status_code == 403
    assert client.post(BASE + "/intents", content=raw, headers=signed(raw, stamp=int(time.time()) - 301)).status_code == 403
    assert client.post(BASE + "/intents", content=raw, headers=signed(raw, Origin="https://evil.test")).status_code == 403
    monkeypatch.delenv("OPORA_EXECUTION_OBSERVERS")
    assert post(client, "/intents", body).status_code == 403


def test_late_accounting_never_restores_authority_and_terminated_is_absorbing(broker):
    client, body, lease = broker
    bound = post(client, "/intents", body).json()
    db = client.app.state.service.db_for("draft")
    with db:
        db.execute("UPDATE card_leases SET expires_at=0 WHERE node_id=?", (lease["nodeId"],))
    first = observation(bound, status="terminated", providerStatus="terminated")
    result = post(client, "/observations", first)
    assert result.status_code == 200, result.text
    replay = post(client, "/intents", body)
    assert replay.status_code == 200 and replay.json()["authorityActive"] is False
    second = {**first, "requestId": "later", "sequence": 2, "expectedObservationHead": result.json()["id"]}
    assert post(client, "/observations", {**second, "status": "running", "providerStatus": "running"}).status_code == 409
    second["cumulative"] = {**second["cumulative"], "inputTokens": 20, "listCostCents": "101"}
    assert post(client, "/observations", second).status_code == 200
    assert client.get(BASE, params=SCOPE, headers=AGENT).json()["items"][0]["listBudgetExceeded"]
    assert db.execute("SELECT expires_at FROM card_leases WHERE node_id=?", (lease["nodeId"],)).fetchone()[0] == 0


@pytest.mark.parametrize("raw", [b'{"project":"draft","project":"draft"}', b'{"x":NaN}', b'{"x":' + b'[' * 70 + b'0' + b']' * 70 + b'}'])
def test_strict_json_rejected_before_business_logic(broker, raw):
    client, _, _ = broker
    assert client.post(BASE + "/intents", content=raw, headers=signed(raw)).status_code == 409


def test_chunked_oversize_stops_before_authentication(broker, monkeypatch):
    client, _, _ = broker
    from backend.api.editor import opora_execution_observer_routes as routes
    monkeypatch.setattr(routes, "authenticate", lambda *_: pytest.fail("oversized request reached authentication"))
    response = client.post(BASE + "/intents", content=iter([b"x" * 65536] * 3), headers={"Origin": ORIGIN, "Content-Type": "application/json"})
    assert response.status_code == 413


def test_project_rollback_keeps_global_reservation_and_missing_registry_refuses_history(broker, monkeypatch):
    from database.repositories import opora_execution_observers as storage
    client, body, _ = broker
    bound = post(client, "/intents", body).json()
    first = observation(bound)
    original = storage.PROJECT_LIMIT
    monkeypatch.setattr(storage, "PROJECT_LIMIT", 0)
    assert post(client, "/observations", first).status_code == 409
    canvas = client.app.state.service
    assert canvas.db_for("draft").execute("SELECT COUNT(*) FROM opora_execution_observations").fetchone()[0] == 0
    assert canvas.db.execute("SELECT intent_id FROM opora_execution_observer_sessions").fetchone()[0] == bound["id"]
    monkeypatch.setattr(storage, "PROJECT_LIMIT", original)
    assert post(client, "/observations", first).status_code == 200
    # Simulate a mismatched historical registry restore, never auto-recreate it.
    with canvas.registry_lock, canvas.db:
        canvas.db.execute("DROP TRIGGER opora_execution_observer_sessions_delete")
        canvas.db.execute("DELETE FROM opora_execution_observer_sessions")
    assert client.get(BASE, params=SCOPE, headers=AGENT).status_code == 409
    assert post(client, "/observations", first).status_code == 409
    assert canvas.db.execute("SELECT COUNT(*) FROM opora_execution_observer_sessions").fetchone()[0] == 0


def test_actual_context_one_with_budget_two_is_bound_without_protocol_downgrade(broker):
    client, first_body, _ = broker
    canvas = client.app.state.service
    authority = ExecutionResults(canvas)
    # A second real accepted node has no lease or budget family yet.
    nodes = canvas.view("draft", "draft")["graph"]["nodes"]
    node = next(item["id"] for item in nodes if item["id"] != first_body["nodeId"])
    context = authority.context(**SCOPE, node=node)
    policy = ExecutionBudgets(canvas).configure({**SCOPE, "nodeId": node, "expectedPolicyHead": None,
        "expectedAcceptedHead": context["acceptedHead"], "requestId": "policy-context-one", "limits": {
            "maxRunSeconds": 60, "maxAttempts": 3, "maxRepairRounds": 1}}, HUMAN)
    lease = authority.claim({**SCOPE, "nodeId": node, "requestId": "claim-context-one", "ttlSeconds": 60,
        "expectedAcceptedHead": context["acceptedHead"], "expectedContextVersion": context["contextVersion"],
        "expectedBudgetPolicyHead": policy["policyHead"], "previousExecutionId": None}, "agent:worker")
    body = {**first_body, **{key: lease[key] for key in ("executionId", "nodeId", "epoch", "acceptedRevision", "assignmentDigest", "budget")},
            "requestId": "intent-context-one", "contextProtocolVersion": 1,
            "contextVersion": lease["assignment"]["contextVersion"], "authorityDeadlineAt": lease["budget"]["runDeadlineAt"]}
    response = post(client, "/intents", body)
    assert response.status_code == 200, response.text
    assert response.json()["contextProtocolVersion"] == 1 and response.json()["executionProtocolVersion"] == 2
    assert response.json()["budget"] == lease["budget"]
