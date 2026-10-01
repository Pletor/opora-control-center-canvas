"""Podklady nesou akce, pravidla uzlu a vazby s portem, aby agent věděl, co má dělat a jak."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
SCOPE = {"project": "draft", "workspace": "draft"}


def _seed(client):
    view = client.get("/api/view", params=SCOPE).json()
    graph = {
        "nodes": [
            {"id": "login", "parentId": None, "kind": "node", "name": "Přihlášení", "purpose": "", "x": 0, "y": 0},
            {"id": "menu", "parentId": None, "kind": "node", "name": "Menu", "purpose": "", "x": 300, "y": 0},
            {"id": "audit", "parentId": None, "kind": "node", "name": "Audit", "purpose": "", "x": 300, "y": 200},
        ],
        "edges": [
            {"id": "e-next", "source": "login", "target": "menu", "port": "next"},
            {"id": "e-action", "source": "login", "target": "audit", "port": "action"},
            {"id": "e-legacy", "source": "menu", "target": "audit"},
        ],
    }
    assert client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": graph, "digest": view["digest"]}).status_code == 200
    state = {
        "settings": [], "rules": [], "decisions": [], "tickets": [],
        "nodes": {
            "login": {
                "phase": "discover", "criteria": [], "steps": [],
                "actions": [{"id": "a1", "pipelineId": "verify.tests", "label": "Spustit testy", "params": {}}],
                "rules": [{"id": "r1", "text": "Heslo se nikdy neloguje.", "kind": "must_not"}],
            },
            "menu": {"phase": "discover", "criteria": [], "steps": []},
        },
    }
    assert client.post("/api/desktop-v3/state", headers=HEADERS, json={**SCOPE, "expectedRevision": 0, "state": state}).status_code == 200


def _preview(client, node):
    response = client.post("/api/desktop-v3/packet/preview", headers=HEADERS,
                           json={**SCOPE, "nodeId": node, "path": "", "sessionId": "", "references": [], "note": ""})
    assert response.status_code == 200, response.text
    return response.json()["packet"]


def test_packet_task_carries_node_actions_rules_and_ported_relations(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        _seed(client)
        packet = _preview(client, "login")
        task = packet["task"]
        assert task["actions"] == [{"id": "a1", "pipelineId": "verify.tests", "label": "Spustit testy", "params": {}}]
        assert task["rules"] == [{"id": "r1", "text": "Heslo se nikdy neloguje.", "kind": "must_not"}]
        assert task["next"] == [{"nodeId": "menu", "name": "Menu", "edgeId": "e-next", "port": "next"}]
        relations = {edge["id"]: edge for edge in packet["context"]["relations"]}
        assert relations["e-action"]["port"] == "action"
        assert relations["e-next"]["port"] == "next"
        assert packet["context"]["memory"]["actions"] == task["actions"]


def test_legacy_node_and_edge_default_to_empty_blocks_and_next_port(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        _seed(client)
        task = _preview(client, "menu")["task"]
        assert task["actions"] == [] and task["rules"] == []
        assert task["next"] == [{"nodeId": "audit", "name": "Audit", "edgeId": "e-legacy", "port": "next"}]
