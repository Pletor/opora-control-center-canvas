"""Dohledatelnost: každé ID (uzel, blok, todo, akce, pravidlo, vazba, obrázek) má vlastníka a vstupy/výstupy."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.agent_memory.trace import trace

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
SCOPE = {"project": "draft", "workspace": "draft"}

GRAPH = {
    "nodes": [
        {"id": "login", "parentId": None, "kind": "node", "name": "Přihlášení", "purpose": "", "x": 0, "y": 0},
        {"id": "menu", "parentId": None, "kind": "node", "name": "Menu", "purpose": "", "x": 300, "y": 0},
    ],
    "edges": [{"id": "e1", "source": "login", "target": "menu", "port": "next"}],
}


def _branch(kind="none", target="", note=""):
    return {"kind": kind, "targetId": target, "note": note}


STATE = {
    "settings": [], "rules": [], "decisions": [], "tickets": [],
    "nodes": {
        "login": {
            "phase": "discover", "criteria": [], "steps": [],
            "actions": [{"id": "a1", "pipelineId": "verify.run-tests", "label": "Testy", "params": {}}],
            "rules": [{"id": "r1", "text": "Heslo se neloguje.", "kind": "must_not"}],
            "blocks": [
                {"id": "b1", "number": "1", "title": "Formulář", "text": "", "tags": ["auth", "ui"],
                 "todos": [{"id": "t1", "text": "Pole e-mail", "done": True, "assignee": ""}],
                 "images": [{"id": "i1", "path": "docs/login.png", "caption": ""}],
                 "state": {"status": "met", "condition": "Formulář odeslán", "onMet": _branch("block", "b2"), "onUnmet": _branch("action", "a1")},
                 "parentBlockId": ""},
                {"id": "b2", "number": "1.1", "title": "Ověření", "text": "", "tags": ["auth"], "todos": [], "images": [],
                 "state": {"status": "open", "condition": "", "onMet": _branch("node", "menu"), "onUnmet": _branch()},
                 "parentBlockId": "b1"},
            ],
        },
    },
}


def test_trace_resolves_every_kind_with_owner_and_links():
    assert trace(STATE, GRAPH, "b1") == {
        "id": "b1", "kind": "block", "nodeId": "login", "blockId": "b1", "number": "1", "label": "Formulář",
        "parentBlockId": "",
        "incoming": [],
        "outgoing": [
            {"via": "onMet", "kind": "block", "targetId": "b2", "label": "Ověření"},
            {"via": "onUnmet", "kind": "action", "targetId": "a1", "label": "Testy"},
        ],
    }
    b2 = trace(STATE, GRAPH, "b2")
    assert b2["incoming"] == [{"via": "onMet", "kind": "block", "sourceId": "b1", "label": "Formulář"}]
    assert b2["outgoing"] == [{"via": "onMet", "kind": "node", "targetId": "menu", "label": "Menu"}]
    assert trace(STATE, GRAPH, "t1") == {"id": "t1", "kind": "todo", "nodeId": "login", "blockId": "b1", "label": "Pole e-mail", "done": True}
    assert trace(STATE, GRAPH, "i1") == {"id": "i1", "kind": "image", "nodeId": "login", "blockId": "b1", "path": "docs/login.png"}
    a1 = trace(STATE, GRAPH, "a1")
    assert a1["kind"] == "action" and a1["nodeId"] == "login"
    assert a1["incoming"] == [{"via": "onUnmet", "kind": "block", "sourceId": "b1", "label": "Formulář"}]
    assert trace(STATE, GRAPH, "r1") == {"id": "r1", "kind": "rule", "nodeId": "login", "label": "Heslo se neloguje.", "ruleKind": "must_not"}
    assert trace(STATE, GRAPH, "e1") == {"id": "e1", "kind": "edge", "source": "login", "target": "menu", "port": "next"}
    menu = trace(STATE, GRAPH, "menu")
    assert menu["kind"] == "node" and menu["incoming"] == [
        {"via": "edge", "kind": "node", "sourceId": "login", "label": "Přihlášení", "port": "next"},
        {"via": "onMet", "kind": "block", "sourceId": "b2", "label": "Ověření"},
    ]
    assert trace(STATE, GRAPH, "ghost") is None


def test_endpoint_serves_trace(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        view = client.get("/api/view", params=SCOPE).json()
        assert client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": GRAPH, "digest": view["digest"]}).status_code == 200
        assert client.post("/api/desktop-v3/state", headers=HEADERS, json={**SCOPE, "expectedRevision": 0, "state": STATE}).status_code == 200
        found = client.get("/api/desktop-v3/trace", params={**SCOPE, "id": "t1"})
        assert found.status_code == 200 and found.json()["kind"] == "todo"
        missing = client.get("/api/desktop-v3/trace", params={**SCOPE, "id": "ghost"})
        assert missing.status_code == 404
