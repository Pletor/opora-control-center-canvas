from fastapi.testclient import TestClient

from backend import agent_routes, agent_sources
from backend.app import create_app


def test_process_adapter_reuses_the_registered_transport(monkeypatch, tmp_path):
    calls = []

    def fixture_fetch(path):
        if path == "/api/process":
            # Kanonický tvar /api/process používá klíč "run" (viz test_oporacc_process_source);
            # adaptér si cizí klíč nedomýšlí, fixture proto drží skutečný kontrakt zdroje.
            return 200, {"runs": [{"run": "isolated-fixture", "state": "completed"}]}
        return 200, {"status": "ok", "projects": []}

    def forbidden_live_fetch(self, path):
        calls.append(path)
        raise AssertionError("Test transport must not fall back to real OporaCC")

    registered = agent_sources.PlatnoSource(fetch=fixture_fetch)
    monkeypatch.setattr(agent_routes, "PlatnoSource", lambda *_a, **_k: registered)
    monkeypatch.setattr(agent_sources.OporaProcessSource, "_http_fetch", forbidden_live_fetch)
    monkeypatch.setenv("OPORA_AGENT_ORCHESTRATOR_ROOT", str(tmp_path / "no-lanes"))
    with TestClient(create_app(tmp_path / "data"), base_url="http://127.0.0.1:8740") as client:
        response = client.get("/api/agents/runs", headers={"Origin": "http://127.0.0.1:8740"})
        assert calls == [], "A nested source bypassed the explicitly registered transport"
        assert response.status_code == 200
        assert any(run["runId"] == "isolated-fixture" for run in response.json()["items"])
