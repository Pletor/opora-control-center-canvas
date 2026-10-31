"""`GET /api/oporahub/card-trail`: stopa práce karty nad skutečnými záznamy exekucí, jen čtení."""
import pytest

from backend.api.editor.card_trail_routes import create_card_trail_router
from backend.api.editor.test_opora_changeset_routes import AGENT
from backend.api.editor.test_opora_execution_routes import BASE, payload
from backend.api.editor.test_opora_execution_routes import (
    client as client,  # noqa: PLC0414 - shared pytest fixture
)
from backend.canvas.test_canvas_plan import HEADERS, SCOPE

TRAIL = "/api/oporahub/card-trail"


def read(client, headers=AGENT, **params):
    if not any(getattr(route, "path", "") == TRAIL for route in client.app.routes):
        client.app.router.routes[0:0] = create_card_trail_router(client.app.state.service).routes
    return client.get(TRAIL, params={**SCOPE, "node": "n0", **params}, headers=headers)


def test_running_then_reported_run(client):
    execution = client.post(BASE + "/claim", headers=AGENT, json=payload(client)).json()
    running = read(client)
    assert running.status_code == 200, running.text
    body = running.json()
    assert body["nodeId"] == "n0"
    assert body["now"]["owner"] == "agent:builder" and body["now"]["source"] == "det"
    assert body["runs"][0]["executionId"] == execution["executionId"] and body["runs"][0]["state"] == "running"
    assert execution["token"] not in running.text
    assert any(item["kind"] == "lease.claimed" for item in body["recent"])

    submitted = client.post(BASE + "/" + execution["executionId"] + "/results", headers=AGENT, json={
        **SCOPE, "token": execution["token"], "epoch": execution["epoch"], "requestId": "r1",
        "result": {"summary": "Hotová práce"}})
    assert submitted.status_code == 200, submitted.text
    body = read(client).json()
    (run,) = body["runs"]
    assert run["state"] == "reported" and run["summary"] == "Hotová práce" and run["source"] == "agent"
    assert body["now"] is None and body["judgment"] == []
    assert {"nodeId", "now", "runs", "pr", "missing", "recent", "ports", "judgment"} <= set(body)


def test_read_writes_nothing(client):
    service = client.app.state.service
    before = service.db_for("draft").total_changes
    assert read(client).status_code == 200
    assert service.db_for("draft").total_changes == before


def test_identity_required(client):
    assert read(client, headers=HEADERS).status_code == 200  # člověk s relačním dokladem UI
    client.cookies.clear()
    assert read(client, headers=HEADERS).status_code == 428  # bez dokladu a bez hlavičky agenta


@pytest.mark.parametrize("node", ["", "../n0", "n0 n1", "x" * 81])
def test_invalid_node_is_conflict(client, node):
    assert read(client, node=node).status_code == 409
