"""Výstup modelu: stav bloků, zprávy na vazbách, návrh uzavření a rozhodnutí pod CAS revizí."""
import copy

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
SCOPE = {"project": "draft", "workspace": "draft"}
EMPTY = {"settings": [], "rules": [], "decisions": [], "nodes": {}, "tickets": [], "edges": {}}

GRAPH = {
    "nodes": [
        {"id": "focus", "parentId": None, "kind": "node", "name": "Ohnisko", "purpose": "", "x": 0, "y": 0},
        {"id": "dalsi", "parentId": None, "kind": "node", "name": "Další", "purpose": "", "x": 300, "y": 0},
    ],
    "edges": [{"id": "e-out", "source": "focus", "target": "dalsi", "port": "block",
               "sourceBlockId": "b1", "sourcePortId": "p1"}],
}


def branch():
    return {"kind": "none", "targetId": "", "note": ""}


def block(bid, number, **overrides):
    item = {
        "id": bid, "number": number, "title": f"Blok {number}", "text": "", "tags": [], "todos": [], "images": [],
        "state": {"status": "open", "condition": "", "onMet": branch(), "onUnmet": branch()},
        "parentBlockId": "",
    }
    item.update(overrides)
    return item


def base_state():
    value = copy.deepcopy(EMPTY)
    value["nodes"] = {"focus": {
        "phase": "discover", "criteria": [], "steps": [],
        "blocks": [block("b1", "1", ports=[{"id": "p1", "label": "Návrh"}]), block("b2", "2")],
    }}
    return value


def output(**overrides):
    item = {
        "schema": "opora.agent-output/1",
        "blocks": [{"blockId": "b1", "status": "met", "note": "Hotovo."}],
        "reports": [{"edgeId": "e-out", "log": "Krok za krokem.", "summary": "Router hotový.",
                     "handoff": "Pokrač u testu.", "improvements": "Chybí fixture.", "errors": ""}],
        "done": {"proposed": True, "note": "Podle mě hotovo."},
        "decisions": ["Router zůstává tenký."],
    }
    item.update(overrides)
    return item


def payload(expected=1, **overrides):
    item = {**SCOPE, "nodeId": "focus", "expectedRevision": expected, "agent": "sonnet/impl",
            "output": output()}
    item.update(overrides)
    return item


def prepared(client, state=None):
    view = client.get("/api/view", params=SCOPE).json()
    assert client.post("/api/graph", headers=HEADERS,
                       json={**SCOPE, "graph": GRAPH, "digest": view["digest"]}).status_code == 200
    saved = client.post("/api/desktop-v3/state", headers=HEADERS,
                        json={**SCOPE, "expectedRevision": 0, "state": state or base_state()})
    assert saved.status_code == 200, saved.text
    return saved.json()["revision"]


def send(client, body):
    return client.post("/api/desktop-v3/agent-output", headers=HEADERS, json=body)


def test_output_writes_block_status_edge_report_done_proposal_and_decision(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client)
        response = send(client, payload(revision))
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["revision"] == revision + 1 and result["readOnly"] is False
        node = result["state"]["nodes"]["focus"]
        assert node["blocks"][0]["state"]["status"] == "met"
        assert node["blocks"][1]["state"]["status"] == "open"
        assert node["done"]["by"] == "agent" and node["done"]["confirmed"] is False
        assert node["done"]["note"] == "Podle mě hotovo." and node["done"]["at"]
        report = result["state"]["edges"]["e-out"]
        assert report["summary"] == "Router hotový." and report["by"] == "agent"
        assert report["agent"] == "sonnet/impl" and report["updatedAt"]
        decision = result["state"]["decisions"][0]
        assert decision["text"] == "Router zůstává tenký." and decision["by"] == "agent"
        assert decision["nodeId"] == "focus" and decision["path"] == "" and decision["pinned"] is False
        assert decision["createdAt"]


def test_done_without_proposal_leaves_the_card_open(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client)
        body = payload(revision, output=output(done={"proposed": False, "note": ""}))
        result = send(client, body).json()
        assert "done" not in result["state"]["nodes"]["focus"]


def test_closed_card_refuses_the_output(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        state = base_state()
        state["nodes"]["focus"]["done"] = {"confirmed": True, "at": "2026-09-14T08:00:00+00:00",
                                           "by": "human", "note": "Zavřeno."}
        revision = prepared(client, state)
        response = send(client, payload(revision))
        assert response.status_code == 409 and "uzavřen" in response.json()["error"].lower()
        current = client.get("/api/desktop-v3/state", params=SCOPE).json()
        assert current["revision"] == revision and current["state"]["edges"] == {}


def test_stale_revision_is_refused_and_nothing_is_written(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client)
        assert send(client, payload(revision)).status_code == 200
        again = send(client, payload(revision))
        assert again.status_code == 409 and "revi" in again.json()["error"].lower()
        assert client.get("/api/desktop-v3/state", params=SCOPE).json()["revision"] == revision + 1


@pytest.mark.parametrize("body_change", [
    {"output": output(blocks=[{"blockId": "bX", "status": "met", "note": ""}])},
    {"output": output(reports=[{"edgeId": "eX", "log": "", "summary": "", "handoff": "",
                                "improvements": "", "errors": ""}])},
    {"nodeId": "nikdo"},
])
def test_unknown_block_edge_or_node_writes_nothing(tmp_path, body_change):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client)
        response = send(client, payload(revision, **body_change))
        assert response.status_code == 409, response.text
        current = client.get("/api/desktop-v3/state", params=SCOPE).json()
        assert current["revision"] == revision
        assert current["state"]["edges"] == {} and current["state"]["decisions"] == []
        assert current["state"]["nodes"]["focus"]["blocks"][0]["state"]["status"] == "open"


@pytest.mark.parametrize("body_change", [
    {"output": output(schema="opora.agent-output/2")},
    {"output": output(blocks=[{"blockId": "b1", "status": "open", "note": ""}])},
    {"output": output(blocks=[{"blockId": "b1", "status": "met"}])},
    {"output": output(blocks=[{"blockId": "b1", "status": "met", "note": ""},
                              {"blockId": "b1", "status": "unmet", "note": ""}])},
    {"output": output(reports=[{"edgeId": "e-out", "log": "x" * 4001, "summary": "", "handoff": "",
                                "improvements": "", "errors": ""}])},
    {"output": output(done={"proposed": "ano", "note": ""})},
    {"output": output(done={"proposed": True})},
    {"output": output(decisions=[""])},
    {"output": output(decisions=[5])},
    {"agent": "a" * 121},
    {"expectedRevision": -1},
    {"expectedRevision": "1"},
    {"extra": 1},
])
def test_malformed_output_is_rejected(tmp_path, body_change):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client)
        assert send(client, payload(revision, **body_change)).status_code == 409


def test_successor_cannot_overwrite_predecessor_report(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client)
        assert send(client, payload(revision)).status_code == 200
        before = client.get("/api/desktop-v3/state", params=SCOPE).json()
        forged = payload(before["revision"], nodeId="dalsi", output=output(blocks=[]))
        response = send(client, forged)
        assert response.status_code == 409, response.text
        assert client.get("/api/desktop-v3/state", params=SCOPE).json() == before


def test_card_without_stored_state_accepts_a_done_proposal_and_a_decision(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        revision = prepared(client)
        body = payload(revision, nodeId="dalsi", output=output(blocks=[], reports=[]))
        result = send(client, body).json()
        assert result["state"]["nodes"]["dalsi"]["done"]["by"] == "agent"
        assert result["state"]["decisions"][0]["nodeId"] == "dalsi"
