from fastapi.testclient import TestClient

from backend.app.factory import create_app

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
SCOPE = {"project": "draft", "workspace": "draft"}
GRAPH = {"nodes": [{"id": "karta", "parentId": None, "kind": "node", "name": "Karta", "purpose": "", "x": 0, "y": 0}], "edges": []}
BOARD = {"animation": "kulicka", "duration": 10, "moments": [{"t": 0, "title": "Start"}, {"t": 4, "comment": "Rychleji."}]}


def test_storyboard_roundtrip_and_conflicts(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        digest = client.get("/api/view", params=SCOPE).json()["digest"]
        assert client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": GRAPH, "digest": digest}).status_code == 200
        query = {**SCOPE, "nodeId": "karta"}
        empty = client.get("/api/storyboard", params=query).json()
        assert empty["storyboard"] is None and empty["revision"] == 0 and empty["animations"][0]["id"] == "kulicka"
        body = {**SCOPE, "nodeId": "karta", "expected_revision": 0, "storyboard": BOARD}
        assert client.post("/api/storyboard", headers=HEADERS, json=body).json() == {"revision": 1}
        stale = client.post("/api/storyboard", headers=HEADERS, json=body)
        assert stale.status_code == 409 and "jiném okně" in stale.json()["error"]
        bad = client.post("/api/storyboard", headers=HEADERS, json={**body, "expected_revision": 1, "storyboard": {**BOARD, "fps": 5}})
        assert bad.status_code == 409
        assert client.get("/api/storyboard", params=query).json()["storyboard"]["moments"][1]["comment"] == "Rychleji."
        gone = client.post("/api/storyboard", headers=HEADERS, json={**body, "expected_revision": 1, "storyboard": None})
        assert gone.json() == {"revision": 2}
        assert client.get("/api/storyboard", params=query).json()["storyboard"] is None
