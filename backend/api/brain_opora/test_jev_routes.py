"""Routy nastavení Jev: klíče poskytovatelů a povolení kontroly bran (docs/brain-heart-channel.md §5)."""

import sqlite3
import threading

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.brain_opora.jev_routes import create_jev_router
from backend.app.remote_access import is_loopback_only
from backend.memory.memory_service import AppSettings


class FakeCanvas:
    """Jen tabulka `app_settings` a zámek, na kterých stojí skutečné `AppSettings`."""

    def __init__(self):
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.db.execute("CREATE TABLE app_settings(key TEXT PRIMARY KEY, value TEXT)")
        self.registry_lock = threading.RLock()


def jev_app(monkeypatch, actor="human", provider="typesafe"):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("CELERIS_API_KEY", raising=False)
    settings = AppSettings(FakeCanvas())
    app = FastAPI()

    @app.middleware("http")
    async def as_actor(request, call_next):
        request.state.actor = actor
        return await call_next(request)

    app.include_router(create_jev_router(settings, provider))
    return app, settings


def test_jev_key_is_stored_but_never_returned(monkeypatch):
    app, _settings = jev_app(monkeypatch)
    with TestClient(app) as client:
        assert client.get("/api/brain/jev").json() == {
            "configured": False, "provider": "typesafe", "keys": {"typesafe": False, "celeris": False}}
        saved = client.post("/api/brain/jev/key", json={"key": "ts-secret"})
        assert saved.json()["jev"]["configured"] is True and "ts-secret" not in saved.text
        status = client.get("/api/brain/jev").json()
        assert status == {"configured": True, "provider": "typesafe", "keys": {"typesafe": True, "celeris": False}}
        assert "ts-secret" not in str(status)
        assert client.post("/api/brain/jev/key", json={"key": "a b"}).status_code == 422
        assert client.post("/api/brain/jev/key", json={"key": "x", "more": 1}).status_code == 422
        assert client.post("/api/brain/jev/key", json={"key": None}).json()["jev"]["configured"] is False


def test_celeris_key_is_separate_and_never_returned(monkeypatch):
    app, settings = jev_app(monkeypatch, provider="celeris")
    with TestClient(app) as client:
        saved = client.post("/api/brain/jev/key", json={"key": "cel-secret", "provider": "celeris"})
        assert saved.status_code == 200 and "cel-secret" not in saved.text
        assert saved.json()["jev"] == {"configured": True, "provider": "celeris", "keys": {"typesafe": False, "celeris": True}}
        assert settings.celeris_key() == "cel-secret" and settings.typesafe_key() is None
        assert client.post("/api/brain/jev/key", json={"key": "x", "provider": "openai"}).status_code == 422
        assert "cel-secret" not in client.get("/api/brain/jev").text


def test_agent_cannot_set_key(monkeypatch):
    app, settings = jev_app(monkeypatch, actor="agent")
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.post("/api/brain/jev/key", json={"key": "ts-secret"}).status_code >= 400
        assert settings.typesafe_key() is None


def test_gate_check_permission_is_human_only(monkeypatch):
    app, settings = jev_app(monkeypatch)
    with TestClient(app) as client:
        assert client.get("/api/brain/jev/gate-check", params={"project": "p1"}).json() == {
            "project": "p1", "allowed": {"typesafe": False, "celeris": False}}
        allowed = client.post("/api/brain/jev/gate-check", json={"project": "p1", "provider": "celeris", "allowed": True})
        assert allowed.json() == {"project": "p1", "allowed": {"typesafe": False, "celeris": True}}
        assert settings.gate_check_allowed("p1", "celeris") and not settings.gate_check_allowed("p1", "typesafe")
        assert not settings.gate_check_allowed("p2", "celeris")
        assert client.post("/api/brain/jev/gate-check",
                           json={"project": "p1", "provider": "celeris", "allowed": "ano"}).status_code == 422
        client.post("/api/brain/jev/gate-check", json={"project": "p1", "provider": "celeris", "allowed": False})
        assert not settings.gate_check_allowed("p1", "celeris")
    agent_app, agent_settings = jev_app(monkeypatch, actor="agent")
    with TestClient(agent_app, raise_server_exceptions=False) as client:
        refused = client.post("/api/brain/jev/gate-check", json={"project": "p1", "provider": "celeris", "allowed": True})
        assert refused.status_code >= 400
        assert agent_settings.gate_check_permissions() == {}


def test_jev_settings_are_loopback_only():
    assert is_loopback_only("/api/brain/jev") and is_loopback_only("/api/brain/jev/key")
    assert is_loopback_only("/api/brain/jev/gate-check")
    assert not is_loopback_only("/api/brain/jevx")
