"""Podklady: velký obraz všech bloků, ale jen jeden aktuální krok jako úkol."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
SCOPE = {"project": "draft", "workspace": "draft"}


def _branch(kind="none", target="", note=""):
    return {"kind": kind, "targetId": target, "note": note}


def _seed(client):
    view = client.get("/api/view", params=SCOPE).json()
    graph = {"nodes": [{"id": "login", "parentId": None, "kind": "node", "name": "Přihlášení", "purpose": "", "x": 0, "y": 0}], "edges": []}
    assert client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": graph, "digest": view["digest"]}).status_code == 200
    state = {
        "settings": [], "rules": [], "decisions": [], "tickets": [],
        "nodes": {"login": {
            "phase": "discover", "criteria": [], "steps": [],
            "actions": [{"id": "a1", "pipelineId": "verify.run-tests", "label": "Testy", "params": {}}],
            "rules": [{"id": "r1", "text": "Heslo se neloguje.", "kind": "must_not"}],
            "blocks": [
                {"id": "b1", "number": "1", "title": "Formulář", "text": "Hotové pole.", "tags": ["ui"], "todos": [], "images": [],
                 "state": {"status": "met", "condition": "", "onMet": _branch("block", "b2"), "onUnmet": _branch()}, "parentBlockId": ""},
                {"id": "b2", "number": "2", "title": "Ověření", "text": "Zkontrolovat heslo.", "tags": ["auth"],
                 "todos": [{"id": "t1", "text": "Hash", "done": False, "assignee": "builder"}],
                 "images": [{"id": "i1", "path": "docs/login.png", "caption": "Vzor"}],
                 "state": {"status": "open", "condition": "Test projde", "onMet": _branch("none"), "onUnmet": _branch("action", "a1")}, "parentBlockId": ""},
                {"id": "b3", "number": "3", "title": "Session", "text": "", "tags": [], "todos": [], "images": [],
                 "state": {"status": "open", "condition": "", "onMet": _branch(), "onUnmet": _branch()}, "parentBlockId": ""},
            ],
        }},
    }
    assert client.post("/api/desktop-v3/state", headers=HEADERS, json={**SCOPE, "expectedRevision": 0, "state": state}).status_code == 200


def _preview(client, **extra):
    payload = {**SCOPE, "nodeId": "login", "path": "", "sessionId": "", "references": [], "note": "", **extra}
    response = client.post("/api/desktop-v3/packet/preview", headers=HEADERS, json=payload)
    assert response.status_code == 200, response.text
    return response.json()["packet"]


def test_big_picture_lists_all_blocks_and_current_step_is_first_open_block(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        _seed(client)
        task = _preview(client)["task"]
        assert [b["number"] for b in task["bigPicture"]] == ["1", "2", "3"]
        assert task["bigPicture"][0] == {"id": "b1", "number": "1", "title": "Formulář", "status": "met", "tags": ["ui"], "parentBlockId": ""}
        assert "text" not in task["bigPicture"][1]
        step = task["currentStep"]
        assert step["id"] == "b2" and step["text"] == "Zkontrolovat heslo."
        assert step["todos"][0]["assignee"] == "builder"
        assert step["images"] == [{"id": "i1", "path": "docs/login.png", "caption": "Vzor", "contentIncluded": False}]
        assert step["state"]["onUnmet"] == {"kind": "action", "targetId": "a1", "note": "", "label": "Testy"}
        assert task["processes"] == {"actions": task["actions"], "rules": task["rules"]}
        assert "currentStep" in _preview(client)["report"]["note"]


def test_requested_block_id_selects_the_step_and_unknown_block_fails(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        _seed(client)
        assert _preview(client, blockId="b3")["task"]["currentStep"]["id"] == "b3"
        response = client.post("/api/desktop-v3/packet/preview", headers=HEADERS,
                               json={**SCOPE, "nodeId": "login", "path": "", "sessionId": "", "references": [], "note": "", "blockId": "zz"})
        assert response.status_code == 409


def test_node_without_blocks_has_empty_big_picture_and_null_step(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        view = client.get("/api/view", params=SCOPE).json()
        graph = {"nodes": [{"id": "login", "parentId": None, "kind": "node", "name": "Přihlášení", "purpose": "", "x": 0, "y": 0}], "edges": []}
        assert client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": graph, "digest": view["digest"]}).status_code == 200
        task = _preview(client)["task"]
        assert task["bigPicture"] == [] and task["currentStep"] is None
