"""Assignments, returned evidence and OporaHub snapshots share a semantic version."""
import copy

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.graph import digest
from backend.editor.agent_memory.agent_results import AgentResults
from backend.editor.agent_memory.test_agent_output import (
    GRAPH, HEADERS, ORIGIN, SCOPE, output, prepared, send,
)
from backend.editor.agent_packet.specification_context import capture_specification


def brief(client):
    response = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "focus"})
    assert response.status_code == 200, response.text
    return response.json()


def specification(client, node, goal):
    previous = client.get("/api/node-spec", params={**SCOPE, "node": node}).json()
    response = client.post("/api/node-spec", headers=HEADERS, json={
        **SCOPE, "node": node, "expected_revision": previous["revision"],
        "fields": {"goal": goal, "non_goals": "", "acceptance": "Scenario passes"},
    })
    assert response.status_code == 200, response.text


def graph(client, value):
    previous = client.get("/api/view", params=SCOPE).json()
    response = client.post("/api/graph", headers=HEADERS,
                           json={**SCOPE, "graph": value, "digest": previous["digest"]})
    assert response.status_code == 200, response.text


def result_request(value):
    return {**value["outputContract"]["request"], "agent": "test-agent", "output": output()}


@pytest.mark.parametrize("changed", ["focus", "parent", "descendant", "drawing", "graph"])
def test_changed_assignment_rejects_result_without_writing(tmp_path, changed):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client)
        tree = copy.deepcopy(GRAPH)
        tree["nodes"][0]["parentId"] = "parent"
        tree["nodes"] += [
            {"id": "parent", "parentId": None, "kind": "sector", "name": "Parent", "purpose": "", "x": 0, "y": 0},
            {"id": "child", "parentId": "focus", "kind": "node", "name": "Child", "purpose": "", "x": 0, "y": 0},
            {"id": "descendant", "parentId": "child", "kind": "node", "name": "Grandchild", "purpose": "", "x": 0, "y": 0},
        ]
        graph(client, tree)
        assignment = brief(client)
        if changed == "drawing":
            response = client.post("/api/drawing", headers=HEADERS, json={
                **SCOPE, "layer": "", "expected_revision": 0,
                "scene": {"elements": [{"id": "wire", "type": "text", "text": "Required screen",
                                         "x": 0, "y": 0, "width": 100, "height": 40}]},
            })
            assert response.status_code == 200, response.text
        elif changed == "graph":
            tree["nodes"][0]["purpose"] = "Changed responsibility"
            graph(client, tree)
        else:
            specification(client, changed, "Changed behavior")
        response = send(client, result_request(assignment))
        assert response.status_code == 409 and "contextVersion" in response.json()["error"]
        assert client.get("/api/desktop-v3/state", params=SCOPE).json()["revision"] == revision
        assert client.get("/api/desktop-v3/agent-results", params={**SCOPE, "nodeId": "focus"}).json()["items"] == []


def test_export_and_saved_result_keep_exact_specification_after_live_edit(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        prepared(client)
        specification(client, "focus", "Original assignment")
        assignment = brief(client)
        assert digest(assignment["specification"]) == assignment["contextVersion"]
        request = result_request(assignment)
        response = send(client, request)
        assert response.status_code == 200, response.text
        record = response.json()["acceptedResult"]
        assert record["binding"] == "bound"
        assert record["contextVersion"] == assignment["contextVersion"]
        assert record["specification"] == assignment["specification"]
        assert record["output"]["blocks"][0]["note"] == "Hotovo."
        # Agent status, decisions and result history cannot change the assignment's version.
        assert brief(client)["contextVersion"] == assignment["contextVersion"]
        specification(client, "focus", "New assignment")
        current = brief(client)
        assert current["contextVersion"] != record["contextVersion"]
        history = client.get("/api/desktop-v3/agent-results", params={**SCOPE, "nodeId": "focus"}).json()
        assert history["items"] == [record] == current["resultHistory"]["items"]


def test_layout_only_change_keeps_version_and_accepts_result(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        prepared(client)
        assignment = brief(client)
        moved = copy.deepcopy(GRAPH)
        moved["nodes"][0].update(x=500, y=900)
        graph(client, moved)
        assert brief(client)["contextVersion"] == assignment["contextVersion"]
        assert send(client, result_request(assignment)).status_code == 200


def test_result_record_failure_rolls_back_state_too(tmp_path, monkeypatch):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        prepared(client)
        assignment = brief(client)
        before = client.get("/api/desktop-v3/state", params=SCOPE).json()

        def fail(*args):
            raise ValueError("Result persistence failed")

        monkeypatch.setattr(AgentResults, "insert", fail)
        response = send(client, result_request(assignment))
        assert response.status_code == 409
        assert client.get("/api/desktop-v3/state", params=SCOPE).json() == before
        assert brief(client)["resultHistory"]["items"] == []


def test_legacy_output_is_explicitly_unbound(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        prepared(client)
        request = result_request(brief(client))
        del request["contextVersion"]
        response = send(client, request)
        assert response.status_code == 200
        record = response.json()["acceptedResult"]
        assert record["binding"] == "legacy-unbound"
        assert record["contextVersion"] is None and record["specification"] is None


def test_readonly_snapshot_marks_unavailable_text_spec_and_drawings(tmp_path, monkeypatch):
    app = create_app(tmp_path / "data")
    with TestClient(app, base_url=ORIGIN) as client:
        prepared(client)
        canvas = app.state.service
        original_view = canvas.view
        monkeypatch.setattr(canvas, "view", lambda *args: {**original_view(*args), "readOnly": True})
        captured = capture_specification(canvas, "draft", "draft", "focus")["specification"]
        assert all(not card["spec"]["available"] and not card["content"]["available"] for card in captured["cards"])
        assert all(not drawing["available"] for drawing in captured["drawings"])
