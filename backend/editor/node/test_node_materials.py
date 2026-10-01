import base64

from fastapi.testclient import TestClient

from backend.app.factory import create_app

ORIGIN = "http://127.0.0.1:8740"
PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\0" * 32).decode()


def prepared(client):
    view = client.get("/api/view").json()
    nodes = [
        {"id": key, "parentId": parent, "kind": kind, "name": key.capitalize(), "purpose": "", "x": 0, "y": 0}
        for key, parent, kind in [("sector", None, "sector"), ("alfa", "sector", "node")]
    ]
    assert client.post(
        "/api/graph",
        headers={"origin": ORIGIN},
        json={"project": "draft", "workspace": "draft", "digest": view["digest"], "graph": {"nodes": nodes, "edges": []}},
    ).status_code == 200


def test_upload_stores_image_in_project_folder_and_serves_it_back(tmp_path):
    root = tmp_path / "data"
    scope = {"project": "draft", "workspace": "draft", "nodeId": "alfa"}
    with TestClient(create_app(root), base_url=ORIGIN) as client:
        prepared(client)
        saved = client.post(
            "/api/node-materials/upload", headers={"origin": ORIGIN},
            json={**scope, "dataUrl": "data:image/png;base64," + PNG},
        )
        assert saved.status_code == 200, saved.text
        name = saved.json()["file"]
        assert name.endswith(".png") and saved.json()["mime"] == "image/png"
        stored = root / "projects" / "draft" / "canvas" / "materials" / "alfa" / name
        assert stored.is_file() and stored.read_bytes().startswith(b"\x89PNG")

        served = client.get("/api/node-materials/file", params={"project": "draft", "nodeId": "alfa", "file": name})
        assert served.status_code == 200 and served.headers["content-type"].startswith("image/png")

        removed = client.post("/api/node-materials/remove", headers={"origin": ORIGIN}, json={"project": "draft", "nodeId": "alfa", "file": name})
        assert removed.json() == {"removed": True}
        assert not stored.exists()
        assert client.get("/api/node-materials/file", params={"project": "draft", "nodeId": "alfa", "file": name}).status_code == 404


def test_upload_rejects_non_images_unknown_nodes_and_path_tricks(tmp_path):
    root = tmp_path / "data"
    with TestClient(create_app(root), base_url=ORIGIN) as client:
        prepared(client)
        text = client.post(
            "/api/node-materials/upload", headers={"origin": ORIGIN},
            json={"project": "draft", "workspace": "draft", "nodeId": "alfa", "dataUrl": "data:text/plain;base64," + PNG},
        )
        assert text.status_code == 409
        missing = client.post(
            "/api/node-materials/upload", headers={"origin": ORIGIN},
            json={"project": "draft", "workspace": "draft", "nodeId": "nikdo", "dataUrl": "data:image/png;base64," + PNG},
        )
        assert missing.status_code == 409
        # Jméno souboru mimo vzor (cesta, jiná složka) se nikdy neotevře.
        assert client.get("/api/node-materials/file", params={"project": "draft", "nodeId": "alfa", "file": "../project.json"}).status_code == 404
        assert client.post("/api/node-materials/remove", headers={"origin": ORIGIN}, json={"project": "draft", "nodeId": "alfa", "file": "../project.json"}).json() == {"removed": False}
