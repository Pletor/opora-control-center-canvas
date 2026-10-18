import base64

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.node.drawing_files import MAX_FILE_BYTES, decode_file, parse_ids

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def image(file_id="img-1", mime="image/png", data=PNG):
    return {"id": file_id, "mimeType": mime, "dataURL": f"data:{mime};base64," + base64.b64encode(data).decode()}


def upload(client, file, scope=None):
    scope = scope or {"project": "draft", "workspace": "draft"}
    return client.post("/api/drawing-file", headers=HEADERS, json={**scope, "file": file})


def test_upload_is_idempotent_and_files_come_back_with_created_time(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        assert upload(client, image()).json() == {"id": "img-1"}
        assert upload(client, image()).status_code == 200
        assert app.state.service.db_for("draft").execute("SELECT COUNT(*) FROM drawing_files").fetchone()[0] == 1
        files = client.get("/api/drawing-files", params={"project": "draft", "workspace": "draft", "ids": "img-1,unknown"}).json()["files"]
        assert len(files) == 1
        assert files[0]["dataURL"] == image()["dataURL"] and files[0]["mimeType"] == "image/png"
        assert isinstance(files[0]["created"], int) and files[0]["created"] > 0
        empty = client.get("/api/drawing-files", params={"project": "draft", "workspace": "draft"})
        assert empty.json() == {"files": []}


@pytest.mark.parametrize(
    "file",
    [
        image(file_id="../bad"),
        image(file_id=""),
        image(file_id="x" * 121),
        image(mime="image/svg+xml"),
        {**image(), "dataURL": "data:image/jpeg;base64," + base64.b64encode(PNG).decode()},
        {**image(), "dataURL": "data:image/png;base64,@@@"},
        {**image(), "dataURL": "https://example.com/a.png"},
        {**image(), "extra": True},
        image(data=b""),
    ],
)
def test_invalid_upload_is_rejected(tmp_path, file):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        assert upload(client, file).status_code == 409


def test_content_must_match_mime_and_same_id_with_other_bytes_is_refused(tmp_path):
    with pytest.raises(ValueError, match="neodpovídá udanému typu"):
        decode_file(image(data=b"\x00" * 24))
    with pytest.raises(ValueError, match="neodpovídá udanému typu"):
        decode_file(image(mime="image/jpeg", data=PNG))
    assert decode_file(image(mime="image/webp", data=b"RIFF\x00\x00\x00\x00WEBPVP8 "))[1] == "image/webp"
    assert decode_file(image(mime="image/jpeg", data=b"\xff\xd8\xff\xe0" + b"\x00" * 8))[1] == "image/jpeg"
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        assert upload(client, image()).status_code == 200
        other = upload(client, image(data=PNG + b"\x01"))
        assert other.status_code == 409 and "jiným obsahem" in other.json()["error"]
        files = client.get("/api/drawing-files", params={"project": "draft", "workspace": "draft", "ids": "img-1"}).json()["files"]
        assert base64.b64decode(files[0]["dataURL"].split(",", 1)[1]) == PNG


def test_oversized_file_is_rejected_before_storage():
    with pytest.raises(ValueError):
        decode_file(image(data=b"\x00" * (MAX_FILE_BYTES + 1)))


def test_large_but_allowed_body_passes_the_request_boundary(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        assert upload(client, image(data=PNG + b"\x01" * (5 * 1024 * 1024))).status_code == 200


def test_id_list_is_limited_and_validated():
    assert parse_ids("a,b,a,") == ["a", "b"]
    with pytest.raises(ValueError):
        parse_ids(",".join(f"i{n}" for n in range(201)))
    with pytest.raises(ValueError):
        parse_ids("ok,../bad")


def test_main_is_read_only_for_upload(tmp_path, monkeypatch):
    app = create_app(tmp_path / "data")
    app.state.service.register_repository("p", "Project", str(tmp_path / "repo"), "fixture://p", "main")

    def fake_git(_root, *args, **_kwargs):
        if args == ("rev-parse", "HEAD"):
            return "a" * 40
        if args == ("branch", "--show-current"):
            return "main"
        return None

    monkeypatch.setattr("backend.canvas.canvas_service.git", fake_git)
    with TestClient(app, base_url=ORIGIN) as client:
        assert upload(client, image(), {"project": "p", "workspace": "main"}).status_code == 409
        listed = client.get("/api/drawing-files", params={"project": "p", "workspace": "main", "ids": "img-1"})
        assert listed.json() == {"files": []}
