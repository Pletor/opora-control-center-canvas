"""Náhled obrázku ze zdroje projektu: jen obrázky, jen uvnitř kořene, chybějící soubor = 404."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da63f8cfc0f01f0005000101b8e0ad3e0000000049454e44ae426082")


def _local_project(client, tmp_path):
    source = tmp_path / "source"
    (source / "docs").mkdir(parents=True)
    (source / "docs" / "login.png").write_bytes(PNG)
    (source / "docs" / "notes.txt").write_text("x", encoding="utf-8")
    response = client.post("/api/local-project", headers=HEADERS, json={"path": str(source), "name": "Zdroj", "confirmed": True})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_image_preview_serves_only_images_inside_the_source(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        project = _local_project(client, tmp_path)
        scope = {"project": project, "workspace": "draft"}
        ok = client.get("/api/workspace/image", params={**scope, "path": "docs/login.png"})
        assert ok.status_code == 200 and ok.headers["content-type"] == "image/png" and ok.content == PNG
        assert client.get("/api/workspace/image", params={**scope, "path": "docs/missing.png"}).status_code == 404
        assert client.get("/api/workspace/image", params={**scope, "path": "docs/notes.txt"}).status_code == 415
        assert client.get("/api/workspace/image", params={**scope, "path": "../secret.png"}).status_code == 409
