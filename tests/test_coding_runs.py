import pytest
from fastapi.testclient import TestClient

from backend.app import create_app

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}


def test_coding_workspace_requires_confirmation_and_never_accepts_target_paths(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        payload = {"project": "draft", "workspace": "draft", "layer": "", "confirmed": True}
        assert client.post("/api/coding/workspaces", headers=HEADERS, json={**payload, "confirmed": False}).status_code == 409
        assert client.post("/api/coding/workspaces", headers=HEADERS, json={**payload, "path": "C:/Users/Admin"}).status_code == 409
        response = client.post("/api/coding/workspaces", headers=HEADERS, json=payload)
        assert response.status_code == 200
        target = response.json()
        assert target["allowedFiles"] == ["calculator.py"]
        assert target["branch"].startswith("work/")
        preview = client.post("/api/coding/preview", headers=HEADERS, json={"targetId": target["id"], "task": "Implement add(a, b) as addition."})
        assert preview.status_code == 200
        assert preview.json()["context"]["policy"]["purpose"] == "coding_sandbox"
        assert client.post("/api/coding/start", headers=HEADERS, json={"targetId": target["id"], "task": "Changed", "digest": preview.json()["digest"], "confirmed": True}).status_code == 409
        assert client.post("/api/coding/preview", headers=HEADERS, json={"targetId": "../escape", "task": "x"}).status_code == 409


def test_scoped_tools_reject_traversal_links_and_test_writes(tmp_path):
    from backend.coding_tools import ScopedFiles
    root = tmp_path / "repo"; root.mkdir()
    (root / "calculator.py").write_text("def add(a, b):\n    return 0\n")
    files = ScopedFiles(root)
    for path in ["../escape.py", "C:/escape.py", ".env", "tests.py", "calculator.py:stream"]:
        with pytest.raises(ValueError):
            files.write(path, "x")
    import hashlib
    written = files.write("calculator.py", "def add(a, b):\n    return a + b\n")
    assert written["sha256"] == hashlib.sha256((root / "calculator.py").read_bytes()).hexdigest()
    assert "a + b" in files.read("calculator.py")
    with pytest.raises(ValueError):
        files.write("calculator.py", "x" * 16001)
