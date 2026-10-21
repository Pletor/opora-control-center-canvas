"""Actual middleware identity and scoped immutable graph API on an empty Canvas."""
import pytest
from fastapi.testclient import TestClient

from backend.api.editor.opora_graph_routes import create_opora_graph_router
from backend.api.editor.test_opora_changeset_routes import AGENT
from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE
from database.schema.opora_graph_schema import SCHEMA

BASE = "/api/oporahub/graph-proposals"


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "data")
    app.state.service.db_for("draft").executescript(SCHEMA)
    if not any(getattr(route, "path", "") == BASE for route in app.routes):
        app.router.routes[0:0] = create_opora_graph_router(app.state.service).routes
    with TestClient(app, base_url=ORIGIN) as instance:
        yield instance


def create(client):
    context = client.get(BASE + "/context", params=SCOPE)
    assert context.status_code == 200, context.text
    context = context.json()
    response = client.post(BASE, headers=AGENT, json={**SCOPE, "parentRevision": context["acceptedHead"],
        "expectedGraphDigest": context["graphDigest"], "subject": "First plan",
        "plan": {"nodes": [{"ref": "task", "kind": "node", "name": "Task"}]}})
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_canvas_agent_proposal_human_accept_and_sparse_history(client):
    item = create(client)
    assert item["by"]["kind"] == "agent" and item["parentRevision"] is None
    payload = {**SCOPE, "expectedAcceptedHead": None, "expectedGraphDigest": item["graphDigest"],
               "adoptBaseGraphDigest": item["graphDigest"]}
    path = BASE + "/" + item["id"]
    assert client.post(path + "/accept", headers=AGENT, json=payload).status_code == 403
    accepted = client.post(path + "/accept", headers=HEADERS, json=payload)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["kind"] == "graph-baseline"
    listed = client.get(BASE, params=SCOPE).json()
    assert listed["items"][0]["accepted"] and "baseGraph" not in listed["items"][0]
    assert client.get(path, params={**SCOPE, "workspace": "other"}).status_code == 409
    assert client.post(path + "/accept", headers=HEADERS, json=payload).json() == accepted.json()


def test_payload_cannot_supply_actor_or_resolved_ids(client):
    item = create(client)
    response = client.post(BASE, headers=AGENT, json={**SCOPE, "parentRevision": None,
        "expectedGraphDigest": item["graphDigest"], "subject": "Spoof", "by": {"kind": "human"},
        "plan": {"nodes": [{"ref": "task", "kind": "node", "name": "Task", "id": "chosen"}]}})
    assert response.status_code == 409
