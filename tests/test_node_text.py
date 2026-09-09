from fastapi.testclient import TestClient

from backend.app import create_app

ORIGIN = "http://127.0.0.1:8740"


def test_text_is_scoped_revisioned_and_part_of_saved_context(tmp_path):
    root = tmp_path / "data"
    with TestClient(create_app(root), base_url=ORIGIN) as client:
        view = client.get("/api/view").json()
        nodes = [{"id": key, "parentId": parent, "kind": kind, "name": key, "purpose": "", "x": 0, "y": 0} for key, parent, kind in [("sector", None, "sector"), ("child", "sector", "node")]]
        assert client.post("/api/graph", headers={"origin": ORIGIN}, json={"project": "draft", "workspace": "draft", "digest": view["digest"], "graph": {"nodes": nodes, "edges": []}}).status_code == 200
        scope = {"project": "draft", "workspace": "draft", "node": "child"}
        text = "První odstavec\n\n<script>alert('text')</script>\n- vnořený kontext"
        saved = client.post("/api/node-text", headers={"origin": ORIGIN}, json={**scope, "expected_revision": 0, "text": text})
        assert saved.status_code == 200
        assert saved.json()["revision"] == 1
        assert client.post("/api/node-text", headers={"origin": ORIGIN}, json={**scope, "expected_revision": 0, "text": "stale"}).status_code == 409
        assert client.get("/api/node-text", params={**scope, "node": "missing"}).status_code == 409
        assert client.get("/api/node-text", params={**scope, "workspace": "main"}).status_code == 409
        context = client.get("/api/llm/preview", params={"project": "draft", "workspace": "draft", "layer": "sector"}).json()["context"]
        assert next(item for item in context["nodeTexts"] if item["nodeId"] == "child")["text"] == text
    with TestClient(create_app(root), base_url=ORIGIN) as client:
        assert client.get("/api/node-text", params=scope).json()["text"] == text
        for invalid in [True, -1, "1"]:
            assert client.post("/api/node-text", headers={"origin": ORIGIN}, json={**scope, "expected_revision": invalid, "text": "x"}).status_code == 409
