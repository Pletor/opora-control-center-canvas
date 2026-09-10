"""Skutečná app musí publikovat agentní API před statickým fallbackem."""

from fastapi.testclient import TestClient

from backend.agent_sources import PlatnoSource
from backend.app import create_app


def test_real_app_exposes_agent_sources_before_static(tmp_path, monkeypatch):
    monkeypatch.setenv("OPORA_AGENT_ORCHESTRATOR_ROOT", str(tmp_path / "missing-source"))
    monkeypatch.setenv("OPORA_CANVAS_PORT", "8740")
    monkeypatch.setattr(PlatnoSource, "_http_fetch", lambda self, path: (None, None))
    app = create_app(tmp_path / "data")
    with TestClient(app, base_url="http://127.0.0.1:8740") as client:
        response = client.get("/api/agents/sources")
        assert response.status_code == 200
        health = response.json()
        assert health["hermes-orchestrator"]["available"] is False
        assert health["oporacc-platno"]["available"] is False
        assert client.get("/api/agents/sources", headers={"Origin": "https://outside.example"}).status_code == 403
        # Veřejné schéma funguje i s líně připojenými routy FastAPI; ploché app.routes ne.
        operation = app.openapi()["paths"]["/api/agents/sources"]
        assert set(operation) == {"get"}
