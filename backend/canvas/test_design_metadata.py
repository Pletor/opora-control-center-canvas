import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.design_metadata import validate_design
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed, send
from backend.canvas.test_canvas_plan_catalog import component


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,hi", "//example.com/x", "https://user:secret@example.com", "https://example.com:bad/x", "https://example.com/\nx", "https://example.com\\x", ""])
def test_design_rejects_unsafe_urls(url):
    with pytest.raises(ValueError):
        validate_design({"artifactUrl": url, "version": "v1"})


def test_design_roundtrip_and_version_changes_specification(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        digest = seed(client)
        plan = component()
        design = {"artifactUrl": "https://example.com/artifact", "version": "v1", "previewUrl": "https://example.com/preview.png"}
        plan["nodes"][0]["design"] = design
        response = send(client, digest, plan)
        assert response.status_code == 200, response.text
        node_id = response.json()["refs"]["component"]
        params = {**SCOPE, "nodeId": node_id}
        before = client.get("/api/desktop-v3/node-brief", params=params).json()
        assert before["node"]["design"] == design
        view = client.get("/api/view", params=SCOPE).json()
        node = next(n for n in view["graph"]["nodes"] if n["id"] == node_id)
        node["design"]["version"] = "v2"
        saved = client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": view["graph"], "digest": view["digest"]})
        assert saved.status_code == 200, saved.text
        after = client.get("/api/desktop-v3/node-brief", params=params).json()
        assert before["contextVersion"] != after["contextVersion"]
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        brief = client.get("/api/desktop-v3/node-brief", params=params).json()
        assert brief["node"]["design"]["version"] == "v2"


def test_invalid_design_plan_leaves_graph_unchanged(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        digest = seed(client)
        plan = component()
        plan["nodes"][0]["design"] = {"artifactUrl": "javascript:alert(1)", "version": "v1"}
        result = send(client, digest, plan)
        assert result.status_code == 409, result.text
        assert client.get("/api/view", params=SCOPE).json()["digest"] == digest


@pytest.mark.parametrize("preview", [
    "http://example.com/a.png", "https://localhost/a.png", "https://127.0.0.1/a.png",
    "https://10.0.0.5/a.png", "https://192.168.1.1/a.png", "https://[::1]/a.png", "https://intranet/a.png",
])
def test_preview_must_be_public_https(preview):
    """Kritika #42: náhled se vykreslí jako <img>, nesmí mířit do vnitřní sítě ani přes http."""
    with pytest.raises(ValueError):
        validate_design({"artifactUrl": "https://claude.ai/design/1", "version": "v1", "previewUrl": preview})
    validate_design({"artifactUrl": "https://claude.ai/design/1", "version": "v1", "previewUrl": "https://cdn.example.com/a.png"})
