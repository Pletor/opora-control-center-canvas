"""HTTP capability scope, actor attribution and non-authoritative receipts."""
import pytest
from fastapi.testclient import TestClient

from backend.api.editor.opora_execution_routes import create_opora_execution_router
from backend.api.editor.test_opora_changeset_routes import AGENT, baseline_payload
from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed
from database.schema.opora_execution_schema import SCHEMA

BASE = "/api/oporahub/executions"


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "data")
    app.state.service.db_for("draft").executescript(SCHEMA)
    if not any(getattr(route, "path", "") == BASE + "/claim" for route in app.routes):
        app.router.routes[0:0] = create_opora_execution_router(app.state.service).routes
    with TestClient(app, base_url=ORIGIN) as instance:
        seed(instance)
        assert instance.post("/api/oporahub/baselines", headers=HEADERS, json=baseline_payload(instance)).status_code == 200
        yield instance


def payload(client):
    context = client.get(BASE + "/context", params={**SCOPE, "nodeId": "n0"}).json()
    assert context["available"], context
    return {**SCOPE, "nodeId": "n0", "expectedAcceptedHead": context["acceptedHead"],
            "expectedContextVersion": context["contextVersion"], "requestId": "claim1", "ttlSeconds": 60}


def test_identity_scope_credential_and_receipt(client):
    data = payload(client)
    client.cookies.clear()
    unknown = {"Origin": ORIGIN}
    response = client.post(BASE + "/claim", headers=unknown, json=data)
    assert response.status_code == 428
    response = client.post(BASE + "/claim", headers=AGENT, json=data)
    assert response.status_code == 200, response.text
    record = response.json()
    assert isinstance(record["expiresAt"], (int, float))
    endpoint = BASE + "/" + record["executionId"]
    assert client.get(endpoint + "/assignment", params=SCOPE, headers=AGENT).status_code == 409
    headers = {**AGENT, "X-Opora-Execution-Token": record["token"]}
    read = client.get(endpoint + "/assignment", params=SCOPE, headers=headers)
    assert read.status_code == 200 and "token" not in read.json()
    assert client.get(endpoint + "/assignment", params={**SCOPE, "workspace": "other"}, headers=headers).status_code == 409
    result = {**SCOPE, "token": record["token"], "epoch": record["epoch"], "requestId": "r1", "result": {"summary": "Prepared"}}
    receipt = client.post(endpoint + "/results", headers=AGENT, json=result)
    assert receipt.status_code == 200, receipt.text
    assert client.post(endpoint + "/results", headers=AGENT, json=result).json() == receipt.json()
    assert "token" not in receipt.json()
    history = client.get(BASE, params={**SCOPE, "nodeId": "n0"}, headers=AGENT)
    assert history.status_code == 200 and record["token"] not in history.text
    assert history.json()["executions"][0]["state"] == "reported"
    results = client.get(endpoint + "/results", params=SCOPE, headers=AGENT)
    assert results.json()["results"] == [receipt.json()]
    assert client.get(endpoint + "/results", params={**SCOPE, "workspace": "other"}, headers=AGENT).status_code == 409


@pytest.mark.parametrize("key,value", [("ttlSeconds", True), ("requestId", ""), ("nodeId", []), ("ttlSeconds", 0)])
def test_bad_claim_is_safe_conflict(client, key, value):
    response = client.post(BASE + "/claim", headers=AGENT, json={**payload(client), key: value})
    assert response.status_code == 409
    assert response.json()["code"] == "execution_conflict"


def test_claim_and_heartbeat_can_omit_assignment(client):
    data = payload(client)
    assert client.post(BASE + "/claim", headers=AGENT, params={"assignment": "all"}, json=data).status_code == 409
    assert client.get(BASE, params={**SCOPE, "nodeId": "n0"}, headers=AGENT).json()["executions"] == []
    slim = client.post(BASE + "/claim", headers=AGENT, params={"assignment": "omit"}, json=data)
    assert slim.status_code == 200, slim.text
    lease = slim.json()
    assert "assignment" not in lease and lease["contextVersion"] == data["expectedContextVersion"]
    full = client.post(BASE + "/claim", headers=AGENT, json=data).json()  # replay, default view
    assert full["assignment"]["contextVersion"] == lease["contextVersion"]
    assert {key: value for key, value in full.items() if key not in ("assignment", "serverNow")} == {
        key: value for key, value in lease.items() if key not in ("contextVersion", "serverNow")}
    endpoint = BASE + "/" + lease["executionId"] + "/heartbeat"
    body = {**SCOPE, "token": lease["token"], "epoch": lease["epoch"], "ttlSeconds": 60}
    beat = client.post(endpoint, headers=AGENT, params={"assignment": "omit"}, json=body)
    assert beat.status_code == 200 and "assignment" not in beat.json() and beat.json()["state"] == "running"
    assert len(beat.content) * 2 < len(client.post(endpoint, headers=AGENT, json=body).content)
    read = client.get(BASE + "/" + lease["executionId"] + "/assignment", params=SCOPE,
                      headers={**AGENT, "X-Opora-Execution-Token": lease["token"]})
    assert read.json()["assignment"] == full["assignment"]


def test_step_checkpoint_route_shares_result_authority(client):
    """HTTP shape only; progress across runs is in backend/canvas/test_opora_execution_steps.py."""
    record = client.post(BASE + "/claim", headers=AGENT, json=payload(client)).json()
    endpoint = BASE + "/" + record["executionId"] + "/steps"
    body = {**SCOPE, "token": record["token"], "epoch": record["epoch"], "requestId": "step1",
            "stepId": "s1", "status": "done", "evidence": {"notes": "hotovo", "commits": ["abc1234"]}}
    client.cookies.clear()
    assert client.post(endpoint, headers={"Origin": ORIGIN}, json=body).status_code == 428
    wrong = client.post(endpoint, headers=AGENT, json={**body, "epoch": record["epoch"] + 1})
    assert wrong.status_code == 409 and record["token"] not in wrong.text
    outside = client.post(endpoint, headers=AGENT, json=body)  # this seeded card pins no steps
    assert outside.status_code == 409 and "stepResults" in outside.json()["error"]
