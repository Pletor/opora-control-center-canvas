
import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.domain.service import CanvasService

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}


def post(client, path, payload):
    return client.post(path, headers=HEADERS, json=payload)


def test_local_project_is_metadata_only_and_persists_with_its_draft(tmp_path):
    source = tmp_path / "not-a-git-folder"
    source.mkdir()
    sentinel = source / "untouched.txt"
    sentinel.write_text("do not mutate")
    data = tmp_path / "data"
    with TestClient(create_app(data), base_url=ORIGIN) as client:
        result = post(client, "/api/local-project", {"name": "Local", "path": str(source), "confirmed": True})
        assert result.status_code == 200
        project = result.json()
        assert project["sourceKind"] == "local"
        assert project["sourcePath"] == str(source.resolve())
        assert sentinel.read_text() == "do not mutate"
        duplicate = post(client, "/api/local-project", {"name": "Other", "path": str(source), "confirmed": True})
        assert duplicate.status_code == 200 and duplicate.json()["id"] == project["id"]
        settings = client.get("/api/project-settings", params={"project": project["id"]}).json()
        assert settings["project"]["name"] == "Local" and settings["revision"] == 0
        drawing = client.get("/api/drawing", params={"project": project["id"], "workspace": "draft", "layer": ""})
        assert drawing.status_code == 200 and drawing.json()["readOnly"] is False
    restarted = CanvasService(data)
    assert restarted.project_hub.source_info(restarted.row("projects", project["id"]))["sourcePath"] == str(source.resolve())
    assert sentinel.read_text() == "do not mutate"
    restarted.close()


def test_empty_settings_cas_and_archived_project_are_guarded(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        created = post(client, "/api/empty-project", {"name": "Blank", "confirmed": True})
        assert created.status_code == 200
        pid = created.json()["id"]
        payload = {
            "project": pid,
            "expected_revision": 0,
            "name": "Renamed",
            "settings": {"goal": "Ship", "platform": "web", "provider": "openai-codex", "model": "gpt-5.6", "budgetSeconds": 10},
        }
        saved = post(client, "/api/project-settings", payload)
        assert saved.status_code == 200 and saved.json()["revision"] == 1
        assert saved.json()["project"]["name"] == "Renamed"
        assert post(client, "/api/project-settings", payload).status_code == 409
        preview = client.get("/api/removal-preview", params={"project": pid, "workspace": "main", "kind": "project", "target": pid}).json()
        removed = post(client, "/api/remove", {"project": pid, "workspace": "main", "kind": "project", "target": pid, "digest": preview["digest"], "confirmed": True})
        assert removed.status_code == 200
        assert client.get("/api/project-settings", params={"project": pid}).status_code == 409
        assert post(client, "/api/empty-project", {"name": "Bad", "confirmed": False}).status_code == 409


@pytest.mark.parametrize("path", ["relative", "", None])
def test_local_project_rejects_non_absolute_or_missing_paths(tmp_path, path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        response = post(client, "/api/local-project", {"name": "No", "path": path, "confirmed": True})
        assert response.status_code == 409


@pytest.mark.parametrize("settings", [
    {"goal": "", "platform": "web", "provider": "bad", "model": "bad model", "budgetSeconds": 9},
    {"goal": "x", "platform": "desktop", "provider": "openrouter", "model": "../../bad", "budgetSeconds": 181},
])
def test_settings_schema_and_provider_model_budget_validation(tmp_path, settings):
    service = CanvasService(tmp_path)
    project = service.project_hub.empty_project({"name": "Blank", "confirmed": True})
    with pytest.raises(ValueError):
        service.project_hub.save_settings({"project": project["id"], "expected_revision": 0, "name": "Blank", "settings": settings})
    service.close()
