"""Unrelated canvas activity must not invalidate work or trigger agent retry loops."""

import copy

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.graph import digest
from backend.editor.agent_memory.assignment_snapshots import _insert
from backend.editor.agent_memory.test_agent_output import ORIGIN, SCOPE, prepared, send
from backend.editor.agent_memory.test_versioned_output import (
    brief,
    graph,
    result_request,
    specification,
)
from backend.editor.agent_packet.specification_context import _graph_part


def add_unrelated(client):
    value = client.get("/api/view", params=SCOPE).json()["graph"]
    value["nodes"].append({"id": "audit-note", "parentId": None, "kind": "comment",
                           "name": "Handoff for Claude", "purpose": "FYI", "x": 0, "y": 0})
    graph(client, value)


def test_unrelated_note_keeps_version_and_accepts_inflight_output(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        prepared(client)
        assignment = brief(client)
        add_unrelated(client)
        assert brief(client)["contextVersion"] == assignment["contextVersion"]
        response = send(client, result_request(assignment))
        assert response.status_code == 200, response.text
        status = client.get("/api/desktop-v3/assignment-status", params=SCOPE).json()
        assert status["nodes"]["focus"]["status"] == "current"


@pytest.mark.parametrize("change", [None, "focus", "dalsi"])
def test_legacy_handoff_survives_only_irrelevant_changes(tmp_path, change):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        prepared(client)
        add_unrelated(client)
        assignment = brief(client)
        canvas = client.app.state.service
        legacy = {**assignment["specification"], **_graph_part(canvas, "draft", "draft", canvas.view("draft", "draft"))}
        version = digest(legacy)
        assert version != assignment["contextVersion"]
        saved = _insert(canvas, "draft", "draft", "focus", {"contextVersion": version, "specification": legacy})
        original = copy.deepcopy(saved)
        value = client.get("/api/view", params=SCOPE).json()["graph"]
        next(n for n in value["nodes"] if n["id"] == "audit-note")["name"] = "Updated note"
        graph(client, value)
        if change:
            specification(client, change, "Actual changed requirement")
        params = {**SCOPE, "nodeId": "focus", "id": saved["id"], "source": "handoff"}
        comparison = client.get("/api/desktop-v3/assignment-comparison", params=params).json()
        expected = "changed" if change else "current"
        assert comparison["status"] == expected
        assert client.get("/api/desktop-v3/assignment-status", params=SCOPE).json()["nodes"]["focus"]["status"] == expected
        request = result_request(assignment)
        request["contextVersion"] = version
        response = send(client, request)
        assert response.status_code == (409 if change else 200), response.text
        if not change:
            result = response.json()["acceptedResult"]
            assert result["specification"] == legacy
            assert digest(result["specification"]) == result["contextVersion"] == version
            history = client.get("/api/desktop-v3/agent-results", params={**SCOPE, "nodeId": "focus"}).json()
            assert history["assignmentStatus"][result["id"]] == "current"
        assert saved == original


def test_unknown_version_is_not_rebound(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        prepared(client)
        request = result_request(brief(client))
        request["contextVersion"] = "0" * 64
        assert send(client, request).status_code == 409


def test_area_flow_context_remains_significant():
    from backend.editor.agent_packet.assignment_scope import scoped_specification
    original = {"cards": [{"nodeId": "focus"}], "graph": {
        "nodes": [{"id": "focus", "areaId": "area"}, {"id": "area"}, {"id": "upstream"},
                  {"id": "unrelated"}],
        "edges": [{"id": "flow", "source": "upstream", "target": "area", "port": "flow"}],
    }}
    scoped = scoped_specification(original)
    assert {n["id"] for n in scoped["graph"]["nodes"]} == {"focus", "area", "upstream"}
    assert scoped["graph"]["edges"] == original["graph"]["edges"]
    assert scoped_specification(scoped) == scoped
    removed = copy.deepcopy(original)
    removed["graph"]["edges"] = []
    assert digest(scoped_specification(removed)) != digest(scoped)


@pytest.mark.parametrize("change", ["dependency", "gate", "parent"])
def test_relevant_graph_changes_still_invalidate_assignment(tmp_path, change):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        prepared(client)
        assignment = brief(client)
        value = client.get("/api/view", params=SCOPE).json()["graph"]
        if change == "dependency":
            value["nodes"].append({"id": "dependency", "parentId": None, "kind": "node",
                                   "name": "Dependency", "purpose": "", "x": 0, "y": 0})
            value["edges"].append({"id": "new-dependency", "source": "dependency", "target": "focus", "port": "next"})
        else:
            value["nodes"].append({"id": "sector", "parentId": None, "kind": "sector",
                                   "name": "Sector", "purpose": "", "x": 0, "y": 0})
            next(n for n in value["nodes"] if n["id"] == "focus")["parentId"] = "sector"
            graph(client, value)
            assignment = brief(client)
            if change == "gate":
                next(n for n in value["nodes"] if n["id"] == "sector")["gateNodeId"] = "focus"
            else:
                next(n for n in value["nodes"] if n["id"] == "focus")["parentId"] = None
        graph(client, value)
        assert brief(client)["contextVersion"] != assignment["contextVersion"]
        assert send(client, result_request(assignment)).status_code == 409


def test_customer_journeys_are_not_part_of_the_scoped_assignment():
    """Záznam zachycený, když spec ještě nesla `site.journeys`, se po projekci shoduje s dnešním (§4)."""
    from backend.editor.agent_packet.assignment_scope import same_assignment, scoped_specification

    site = {"kind": "application", "environments": []}

    def spec(app_site):
        return {"cards": [{"nodeId": "app"}], "graph": {"nodes": [{"id": "app", "site": app_site}], "edges": []}}
    legacy = spec({**site, "journeys": [{"id": "j", "name": "J", "from": "nav", "to": "p"}]})
    assert scoped_specification(legacy) == scoped_specification(spec(site))
    assert same_assignment({"contextVersion": "old", "specification": legacy},
                           {"contextVersion": "new", "specification": spec(site)})
