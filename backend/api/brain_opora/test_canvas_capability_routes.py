"""Real middleware, token isolation, native readback and finite dispatch."""
import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.api.brain_opora.canvas_capability_routes import create_canvas_capabilities_router
from backend.brain_opora.determinism import tokens
from database.schema.canvas_session_schema import SCHEMA

BASE = "/api/brain/canvas"
SCOPE = {"project": "draft", "workspace": "draft"}
ORIGIN = "http://127.0.0.1:8740"


@pytest.fixture
def setup(tmp_path):
    app = create_app(tmp_path / "data")
    service = app.state.service
    service.db_for("draft").executescript(SCHEMA)
    if not any(getattr(r, "path", "") == BASE + "/invoke" for r in app.routes):
        app.include_router(create_canvas_capabilities_router(service))
    _, token = tokens.issue_heart(service, "draft", "draft")
    with TestClient(app, base_url=ORIGIN) as client:
        yield client, service, {"origin": ORIGIN, tokens.HEADER: token, "X-Opora-Actor": "agent; name=heart"}


def call(client, headers, capability, data=None, key=None, scope=None):
    body = {**(scope or SCOPE), "capability": capability, "input": data or {}}
    if key is not None:
        body["requestId"] = key
    return client.post(BASE + "/invoke", headers=headers, json=body)


def test_discovery_is_complete_but_honest_and_all_reads_authenticate(setup):
    client, service, auth = setup
    response = client.get(BASE + "/capabilities", params=SCOPE, headers=auth)
    assert response.status_code == 200, response.text
    ops = response.json()["operations"]
    assert len(ops) == 192 and len({o["id"] for o in ops}) == 192
    assert sum(o["implemented"] for o in ops) == 192
    assert response.json()["organizationModel"] == "not_present"
    assert client.get(BASE + "/capabilities", params=SCOPE).status_code == 401
    for scope in ({**SCOPE, "project": "foreign"}, {**SCOPE, "workspace": "main"}):
        assert client.get(BASE + "/capabilities", params=scope, headers=auth).status_code == 403
        assert call(client, auth, "canvas_routes.view", scope=scope).status_code == 403
    assert call(client, auth, "not.a.function").status_code == 422
    assert call(client, auth, "canvas_routes.view", {"path": "/api/graph"}).status_code == 422
    assert client.get(BASE + "/capabilities/canvas_routes.view", params=SCOPE, headers=auth).json()["implemented"]


def test_pending_proposal_readback_replay_and_human_review_preparation(setup):
    client, service, auth = setup
    context = call(client, auth, "opora_graph_routes.context").json()["result"]
    before = service.view("draft", "draft")
    data = {"parentRevision": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
            "subject": "Evidence task", "plan": {"nodes": [{"ref": "task", "kind": "node", "name": "Evidence"}]}}
    first = call(client, auth, "opora_graph_routes.create", data, "cap-test")
    assert first.status_code == 200, first.text
    result = first.json()
    assert result["verified"] and not result["accepted"]
    assert call(client, auth, "opora_graph_routes.create", data, "cap-test").json() == result
    assert call(client, auth, "opora_graph_routes.create", {**data, "subject": "Changed"}, "cap-test").status_code == 409
    assert call(client, auth, "opora_graph_routes.create", {**data, "expectedGraphDigest": "stale"}, "fresh").status_code == 409
    identifier = result["result"]["id"]
    assert call(client, auth, "opora_graph_routes.read", {"identifier": identifier}).json()["result"] == result["result"]
    assert len(call(client, auth, "opora_graph_routes.history").json()["result"]["items"]) == 1
    review = call(client, auth, "opora_graph_routes.accept", {"identifier": identifier})
    assert review.json()["state"] == "awaiting_human" and not review.json()["applied"]
    assert review.json()["proposal"]["id"] == identifier
    assert service.view("draft", "draft")["digest"] == before["digest"]
    assert call(client, auth, "opora_graph_routes.context").json()["result"]["acceptedHead"] is None
    # The ID-only lookup is scoped in its native repository, not looked up globally.
    other = client.post("/api/empty-project", headers={"origin": ORIGIN}, json={"name": "Other", "confirmed": True}).json()["id"]
    _, token = tokens.issue_heart(service, other, "draft")
    foreign = {**auth, tokens.HEADER: token}
    assert call(client, foreign, "opora_graph_routes.read", {"identifier": identifier}, scope={"project": other, "workspace": "draft"}).status_code == 409


def test_session_view_is_private_durable_cas_and_not_browser_applied(setup):
    client, service, auth = setup
    before = service.view("draft", "draft")["digest"]
    data = {"expectedRevision": 0, "view": {"selection": [], "viewport": {"x": 2, "y": 3, "zoom": 1.2}, "filter": "pending"}}
    saved = call(client, auth, "session_view.update", data, "camera")
    assert saved.status_code == 200, saved.text
    assert saved.json()["revision"] == 1 and saved.json()["state"] == "not_applied"
    assert saved.json()["applied"] is False
    assert call(client, auth, "session_view.update", data, "camera").json() == saved.json()
    assert call(client, auth, "session_view.read").json() == saved.json()
    assert call(client, auth, "session_view.update", data, "stale").json()["code"] == "session_view_conflict"
    _, token = tokens.issue_heart(service, "draft", "draft")
    second = call(client, {**auth, tokens.HEADER: token}, "session_view.read").json()
    assert second["revision"] == 0 and second["sessionId"] != saved.json()["sessionId"]
    assert service.view("draft", "draft")["digest"] == before
    invalid = {"expectedRevision": 1, "view": {**data["view"], "selection": ["foreign-node"]}}
    assert call(client, auth, "session_view.update", invalid, "bad-node").status_code == 422


def test_native_graph_search_and_documents(setup):
    from backend.canvas.canvas_plan import apply_plan
    client, service, auth = setup
    view = service.view("draft", "draft")
    written = apply_plan(service, {**SCOPE, "digest": view["digest"], "plan": {"nodes": [
        {"ref": "n", "kind": "node", "name": "Needle", "text": "Evidence source", "spec": {"goal": "A goal"}}]}})
    node = written["refs"]["n"]
    assert call(client, auth, "canvas_routes.view").json()["result"]["digest"] == written["digest"]
    assert "Needle" in call(client, auth, "canvas_routes.canvas_index", {"q": "Needle"}).text
    assert call(client, auth, "node_routes.node_text", {"node": node}).json()["result"]["text"] == "Evidence source"
    assert call(client, auth, "node_routes.node_spec", {"node": node}).json()["result"]["fields"]["goal"] == "A goal"
    from backend.brain_opora.canvas_capabilities import canvas_reads
    inputs = {"canvas_routes.removal_preview": {"kind": "node", "target": node},
              "node_routes.node_links": {"node": node}, "node_routes.node_journal": {"node": node, "day": "2026-11-08"}}
    for capability in canvas_reads.CONTRACTS:
        data = inputs.get(capability, {})
        response = call(client, auth, capability, data)
        assert response.status_code == 200, (capability, response.text)
        assert response.json()["result"] == canvas_reads.read(service, "draft", "draft", capability, data)
    from backend.brain_opora.canvas_capabilities import readiness_reads
    for capability in readiness_reads.CONTRACTS:
        response = call(client, auth, capability)
        assert response.status_code == 200, (capability, response.text)
        actual = response.json()["result"]
        expected = readiness_reads.read(service, "draft", "draft", capability)
        if capability == "desktop_v3_routes.read_source_status":
            from datetime import datetime
            assert datetime.fromisoformat(actual.pop("checkedAt"))
            assert datetime.fromisoformat(expected.pop("checkedAt"))
        if capability == "desktop_v3_routes.read_leases":
            assert isinstance(actual["serverNow"], (int, float))
            assert 0 <= expected.pop("serverNow") - actual.pop("serverNow") < 5
        assert actual == expected
