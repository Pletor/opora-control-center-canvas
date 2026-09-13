import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app

ORIGIN = "http://127.0.0.1:8740"


def test_local_attach_deduplicates_even_with_delayed_creation(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    app = create_app(tmp_path / "data")
    service = app.state.service
    hub = service.project_hub
    original = hub._new
    def delayed(*args):
        time.sleep(0.05)
        return original(*args)
    monkeypatch.setattr(hub, "_new", delayed)
    payload = {"name": "Source", "path": str(source), "confirmed": True}
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _: hub.local_project(payload)["id"], range(2)))
    assert len(set(ids)) == 1
    assert len(service.bootstrap()["projects"]) == 1
    service.close()


def test_settings_cas_across_two_connections(tmp_path, monkeypatch):
    apps = [create_app(tmp_path), create_app(tmp_path)]
    hubs = [app.state.service.project_hub for app in apps]
    first = hubs[0].settings("draft")
    payload = {"project": "draft", "expected_revision": 0, "name": "Changed", "settings": first["settings"]}
    for hub in hubs:
        original = hub._settings
        def delayed(pid, read=original):
            value = read(pid)
            time.sleep(0.05)
            return value
        monkeypatch.setattr(hub, "_settings", delayed)
    def update(hub):
        try:
            hub.save_settings(payload)
            return "saved"
        except ValueError:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(update, hubs)) == ["conflict", "saved"]
    for app in apps:
        app.state.service.close()


@pytest.mark.parametrize("field", ["goal", "platform"])
def test_invalid_settings_types_are_client_errors(tmp_path, field):
    with TestClient(create_app(tmp_path), base_url=ORIGIN, raise_server_exceptions=False) as client:
        original = client.get("/api/project-settings?project=draft").json()
        original["settings"][field] = []
        result = client.post("/api/project-settings", headers={"origin": ORIGIN}, json={"project": "draft", "expected_revision": 0, "name": "Draft", "settings": original["settings"]})
        assert result.status_code == 409
