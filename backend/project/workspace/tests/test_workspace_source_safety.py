import os
import subprocess

import pytest
from fastapi.testclient import TestClient
from backend.project.workspace.tests.test_workspace_sources import ORIGIN, attach

from backend.app.factory import create_app


@pytest.mark.parametrize("path", ["..", "../outside", "/absolute", "C:/Windows", "src//file", "src/./file", "src\\file", "src/NUL.txt", "src/trailing.", "src/trailing ", ".git/config", "x" * 256, "/".join(["x" * 100] * 22)])
def test_invalid_path_refused_before_filesystem(tmp_path, path):
    source = tmp_path / "source"
    source.mkdir()
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        result = client.get("/api/workspace/tree", params={"project": pid, "workspace": "draft", "path": path})
        assert result.status_code == 409
        assert result.json()["error"] == "Neplatná relativní cesta."


def make_link(link, target):
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)
    else:
        link.symlink_to(target, target_is_directory=True)


def test_registered_root_replaced_by_junction_is_refused(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").touch()
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        source.rmdir()
        make_link(source, outside)
        try:
            result = client.get("/api/workspace/tree", params={"project": pid, "workspace": "draft"})
            assert result.status_code == 409
            assert "secret.txt" not in result.text
        finally:
            if os.name == "nt":
                source.rmdir()
            else:
                source.unlink()


def test_child_junction_is_visible_but_cannot_be_traversed(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = source / "escape"
    make_link(link, outside)
    try:
        with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
            pid = attach(client, source)
            params = {"project": pid, "workspace": "draft"}
            tree = client.get("/api/workspace/tree", params=params).json()
            assert tree["entries"][0]["blocked"] is True
            assert client.get("/api/workspace/tree", params={**params, "path": "escape"}).status_code == 409
    finally:
        if os.name == "nt":
            link.rmdir()
        else:
            link.unlink()


def test_source_scope_archive_and_missing_states(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        empty = client.get("/api/workspace/tree", params={"project": "draft", "workspace": "draft"})
        assert empty.status_code == 200 and empty.json()["available"] is False
        assert empty.json()["root"] is None
        assert client.get("/api/workspace/tree", params={"project": "draft", "workspace": "other"}).status_code == 409
        assert client.get("/api/workspace/tree", params={"project": "missing", "workspace": "main"}).status_code == 409
        source = tmp_path / "source"
        source.mkdir()
        pid = attach(client, source)
        assert client.get("/api/workspace/tree", params={"project": pid, "workspace": "main"}).status_code == 409
        source.rmdir()
        assert client.get("/api/workspace/tree", params={"project": pid, "workspace": "draft"}).status_code == 409
