"""Scoped history remains available after every live card has been removed."""
import pytest

from backend.api.editor.test_opora_changeset_routes import AGENT
from backend.api.editor.test_opora_execution_routes import BASE, payload
from backend.api.editor.test_opora_execution_routes import (
    client as client,  # noqa: PLC0414 - shared pytest fixture
)
from backend.canvas.test_canvas_plan import SCOPE


def test_scope_history_survives_empty_canvas_without_private_assignment(client, monkeypatch):
    execution = client.post(BASE + "/claim", headers=AGENT, json=payload(client)).json()
    endpoint = BASE + "/" + execution["executionId"]
    receipt = client.post(endpoint + "/results", headers=AGENT, json={
        **SCOPE, "token": execution["token"], "epoch": execution["epoch"], "requestId": "result",
        "result": {"summary": "Historical work"}})
    assert receipt.status_code == 200
    service = client.app.state.service
    service.save_graph("draft", "draft", {"nodes": [], "edges": []},
                       service.view("draft", "draft")["digest"], allow_removal=True, actor="human")

    def no_live_view(*args, **kwargs):
        raise AssertionError("Reported history must not need a live graph")

    monkeypatch.setattr(service, "view", no_live_view)
    response = client.get(BASE, params=SCOPE, headers=AGENT)
    assert response.status_code == 200, response.text
    rows = response.json()["executions"]
    assert len(rows) == 1 and rows[0]["nodeId"] == "n0"
    assert rows[0]["state"] == "reported"
    assert "token" not in rows[0] and "assignment" not in rows[0]
    assert execution["token"] not in response.text
    filtered = client.get(BASE, params={**SCOPE, "nodeId": "n0"}, headers=AGENT)
    assert filtered.json()["executions"][0]["executionId"] == execution["executionId"]
    assert client.get(endpoint + "/results", params=SCOPE, headers=AGENT).json()["results"] == [receipt.json()]
    for scope in ({**SCOPE, "workspace": "other"}, {**SCOPE, "project": "other"}):
        response = client.get(BASE, params=scope, headers=AGENT)
        assert response.status_code in (200, 409)
        assert execution["executionId"] not in response.text


@pytest.mark.parametrize("node", ["", "../n0", "n0 n1", "x" * 81])
def test_supplied_invalid_history_filter_is_rejected(client, node):
    response = client.get(BASE, params={**SCOPE, "nodeId": node}, headers=AGENT)
    assert response.status_code == 409


@pytest.mark.parametrize("missing", ["project", "workspace"])
def test_scope_history_requires_both_scope_fields(client, missing):
    response = client.get(BASE, params={key: value for key, value in SCOPE.items() if key != missing}, headers=AGENT)
    assert response.status_code == 422
