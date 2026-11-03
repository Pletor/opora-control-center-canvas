
import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.canvas_service import CanvasService
from backend.canvas.site_settings import empty as empty_site

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
            "settings": {"goal": "Ship", "platform": "web", "architecture": "", "tenancy": "", "site": empty_site()},
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


PROFILE = {"architecture": "", "tenancy": "", "site": empty_site()}


@pytest.mark.parametrize("settings", [
    {"goal": "x", "platform": "desktop", **PROFILE},
    {"goal": 5, "platform": "web", **PROFILE},
    {"goal": "x" * 4001, "platform": "web", **PROFILE},
    {"goal": "", "platform": "web", **PROFILE, "provider": "openai-codex", "model": "gpt-5.6", "budgetSeconds": 10},
    # Zápis vyžaduje celou sadu klíčů: starý tvar bez profilu neprojde.
    {"goal": "", "platform": "web"},
    {"goal": "", "platform": "web", **PROFILE, "architecture": "soa"},
    {"goal": "", "platform": "web", **PROFILE, "tenancy": "many"},
    {"goal": "", "platform": "web", **PROFILE, "architecture": None},
    # Nastavení webu: celý tvar, bez tajemství.
    {"goal": "", "platform": "web", "architecture": "", "tenancy": ""},
    {"goal": "", "platform": "web", **PROFILE, "site": {**empty_site(), "email": {"from": "", "replyTo": "", "smtpPassword": "x"}}},
])
def test_settings_schema_and_platform_validation(tmp_path, settings):
    service = CanvasService(tmp_path)
    project = service.project_hub.empty_project({"name": "Blank", "confirmed": True})
    with pytest.raises(ValueError):
        service.project_hub.save_settings({"project": project["id"], "expected_revision": 0, "name": "Blank", "settings": settings})
    service.close()


def test_legacy_settings_table_with_llm_columns_stays_readable_and_writable(tmp_path):
    """Starší databáze má NOT NULL sloupce provider/model/budget_seconds; ignorují se, zápis nepadá."""
    import sqlite3

    data = tmp_path / "data"
    data.mkdir()
    db = sqlite3.connect(data / "canvas.sqlite")
    db.executescript("""
        CREATE TABLE project_settings(
            project_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, goal TEXT NOT NULL,
            platform TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
            budget_seconds INTEGER NOT NULL
        );
        INSERT INTO project_settings VALUES('draft', 3, 'Starý cíl', 'app', 'openai-codex', 'gpt-6-astra', 60);
    """)
    db.commit()
    db.close()
    service = CanvasService(data)
    try:
        current = service.project_hub.settings("draft")
        assert current["revision"] == 3
        assert current["settings"] == {"goal": "Starý cíl", "platform": "app", **PROFILE}
        saved = service.project_hub.save_settings({
            "project": "draft", "expected_revision": 3, "name": "Návrh",
            "settings": {"goal": "Nový cíl", "platform": "web", **PROFILE},
        })
        assert saved["revision"] == 4 and saved["settings"] == {"goal": "Nový cíl", "platform": "web", **PROFILE}
    finally:
        service.close()


def test_settings_without_profile_read_with_defaults(tmp_path):
    """Projekt uložený před profilem má řádek v project_settings, ale žádný v project_profile."""
    service = CanvasService(tmp_path)
    try:
        pid = service.project_hub.empty_project({"name": "Starý", "confirmed": True})["id"]
        db = service.db_for(pid)
        db.execute("INSERT INTO project_settings VALUES(?,?,?,?)", (pid, 2, "Starý cíl", "app"))
        db.commit()
        current = service.project_hub.settings(pid)
        assert current["revision"] == 2
        assert current["settings"] == {"goal": "Starý cíl", "platform": "app", **PROFILE}
        # Neznámá hodnota v uloženém profilu (novější verze, ruční zásah) se čte jako nenastaveno.
        db.execute("INSERT INTO project_profile VALUES(?,?,?)", (pid, "mesh", "multi"))
        db.commit()
        assert service.project_hub.settings(pid)["settings"]["architecture"] == ""
        assert service.project_hub.settings(pid)["settings"]["tenancy"] == "multi"
    finally:
        service.close()


def test_profile_round_trip_and_cas(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        pid = post(client, "/api/empty-project", {"name": "Ample", "confirmed": True}).json()["id"]
        fresh = client.get("/api/project-settings", params={"project": pid}).json()
        assert fresh["settings"] == {"goal": "", "platform": "web", **PROFILE}
        profile = {**fresh["settings"], "architecture": "modular", "tenancy": "multi"}
        payload = {"project": pid, "expected_revision": 0, "name": "Ample", "settings": profile}
        saved = post(client, "/api/project-settings", payload)
        assert saved.status_code == 200
        assert saved.json()["revision"] == 1 and saved.json()["settings"] == profile
        stale = post(client, "/api/project-settings", payload)
        assert stale.status_code == 409 and "jiném okně" in stale.json()["error"]
        bad = post(client, "/api/project-settings", {**payload, "expected_revision": 1, "settings": {**profile, "tenancy": "x"}})
        assert bad.status_code == 409 and bad.json()["error"] == "Neplatné rozdělení uživatelů projektu."
        reset = post(client, "/api/project-settings", {**payload, "expected_revision": 1, "settings": fresh["settings"]})
        assert reset.json()["settings"]["architecture"] == "" and reset.json()["revision"] == 2


def test_site_settings_round_trip_in_project_json_and_reject_secrets(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        pid = post(client, "/api/empty-project", {"name": "Web", "confirmed": True}).json()["id"]
        fresh = client.get("/api/project-settings", params={"project": pid}).json()
        site = empty_site()
        site["seo"]["titleTemplate"] = "%s · Zahrada"
        site["design"]["typography"]["h1"] = "Fraunces 48"
        payload = {"project": pid, "expected_revision": 0, "name": "Web", "settings": {**fresh["settings"], "site": site}}
        saved = post(client, "/api/project-settings", payload)
        assert saved.status_code == 200 and saved.json()["settings"]["site"] == site
        assert client.get("/api/project-settings", params={"project": pid}).json()["settings"]["site"] == site
        secret = {**site, "email": {"from": "", "replyTo": "", "smtpPassword": "x"}}
        refused = post(client, "/api/project-settings", {**payload, "expected_revision": 1,
                                                         "settings": {**payload["settings"], "site": secret}})
        assert refused.status_code == 422 and "tajemství" in refused.json()["error"]
        assert refused.json()["field"] == "settings.site.email.smtpPassword"
