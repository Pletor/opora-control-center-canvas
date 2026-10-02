"""`GET /api/canvas-index`: index karet a vazeb ve stejném rozsahu a přístupu jako `/api/view`."""

from fastapi.testclient import TestClient

from backend.app.factory import create_app

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
SCOPE = {"project": "draft", "workspace": "draft"}
GRAPH = {
    "nodes": [
        {"id": "s1", "parentId": None, "kind": "sector", "name": "Editor", "purpose": "", "x": 0, "y": 0},
        {"id": "n1", "parentId": "s1", "kind": "node", "name": "[task] Pop-up tvorby", "purpose": "Dialog",
         "x": 0, "y": 0, "card": {"layer": "backend", "status": "ready"}},
        {"id": "n2", "parentId": "s1", "kind": "node", "name": "Další", "purpose": "", "x": 300, "y": 0},
    ],
    "edges": [{"id": "e1", "source": "n1", "target": "n2"}],
}
STATE = {
    "settings": [], "rules": [], "decisions": [], "tickets": [],
    "nodes": {"n1": {"phase": "discover", "criteria": [], "steps": [],
                     "blocks": [{"id": "b1", "number": "1", "title": "Validace", "text": "", "tags": [],
                                 "todos": [], "images": [], "parentBlockId": "",
                                 "state": {"status": "open", "condition": "",
                                           "onMet": {"kind": "none", "targetId": "", "note": ""},
                                           "onUnmet": {"kind": "none", "targetId": "", "note": ""}}}]}},
    "edges": {"e1": {"log": "", "summary": "", "handoff": "Převezmi", "improvements": "", "errors": "",
                     "updatedAt": "", "by": "human", "agent": "", "sentAt": "", "due": "2026-10-12"}},
}


def seeded(client):
    view = client.get("/api/view", params=SCOPE).json()
    assert client.post("/api/graph", headers=HEADERS,
                       json={**SCOPE, "graph": GRAPH, "digest": view["digest"]}).status_code == 200
    saved = client.post("/api/desktop-v3/state", headers=HEADERS,
                        json={**SCOPE, "expectedRevision": 0, "state": STATE})
    assert saved.status_code == 200, saved.text


def test_index_lists_cards_and_edges_and_searches(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seeded(client)
        everything = client.get("/api/canvas-index", params=SCOPE)
        assert everything.status_code == 200, everything.text
        data = everything.json()
        assert set(data) == {"entries", "total"} and data["total"] == 4
        found = client.get("/api/canvas-index", params={**SCOPE, "q": "validace"}).json()
        assert [row["id"] for row in found["entries"]] == ["n1"]
        assert found["entries"][0]["address"] == "editor/pop-up-tvorby"
        assert found["entries"][0]["type"] == "task" and found["entries"][0]["layer"] == "backend" and found["entries"][0]["status"] == "ready"
        edges = client.get("/api/canvas-index", params={**SCOPE, "q": "druh:edge"}).json()["entries"]
        assert edges[0]["handoff"] == "Převezmi" and edges[0]["due"] == "2026-10-12"
        limited = client.get("/api/canvas-index", params={**SCOPE, "limit": 1}).json()
        assert len(limited["entries"]) == 1 and limited["total"] == 4


def test_empty_draft_has_an_empty_index(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        assert client.get("/api/canvas-index", params=SCOPE).json() == {"entries": [], "total": 0}


def test_scope_errors_match_view(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        for params in ({"project": "neexistuje", "workspace": "draft"}, {"project": "draft", "workspace": "jiny"}):
            view = client.get("/api/view", params=params)
            index = client.get("/api/canvas-index", params=params)
            assert index.status_code == view.status_code and index.status_code >= 400


def test_invalid_limit_is_409(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        assert client.get("/api/canvas-index", params={**SCOPE, "limit": 0}).status_code == 409
        assert client.get("/api/canvas-index", params={**SCOPE, "limit": 2001}).status_code == 409
