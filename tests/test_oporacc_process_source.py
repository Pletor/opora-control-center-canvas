from backend.agents.sources import agent_sources
from backend.agents.sources.agent_catalog import AgentCatalog


def test_oporacc_process_preserves_worktrees_evidence_and_source_times():
    assert hasattr(agent_sources, "OporaProcessSource"), "Chybí read-only adapter skutečného OporaCC procesu"
    calls = []
    def fetch(path):
        calls.append(path)
        return 200, {"runs": [{"run": "wu-tracer", "node_paths": ["src/Board.tsx"],
            "branch": "feat/tracer", "branches": ["feat/tracer"], "worktrees": ["P:/work/tracer"],
            "bridge_run_ids": ["bridge-one"], "state": "WAITING_FOR_DECISION", "updated_at": "2026-09-10T10:00:00Z",
            "axis": [{"name": "TEST", "status": "present", "source": "proof/pytest.txt", "summary": "verified fixture"}]}]}
    source = agent_sources.OporaProcessSource(fetch=fetch)
    catalog = AgentCatalog(process=source)
    page = catalog.list_runs()
    assert page["total"] == 1 and page["items"][0]["runId"] == "wu-tracer"
    run = page["items"][0]
    assert run["sourceTimestamp"] == "2026-09-10T10:00:00Z"
    assert run["worktrees"] == ["P:/work/tracer"] and run["sourcePaths"] == ["src/Board.tsx"]
    assert run["branches"] == ["feat/tracer"] and run["cost"] is None
    detail = catalog.run_detail("oporacc-process", "wu-tracer")
    assert detail["axis"][0]["source"] == "proof/pytest.txt"
    assert detail["parentSessionId"] is None
    assert detail["capabilities"]["btw"]["supported"] is False
    # Detail doplňuje pouze GET telemetrii; žádný dispatch nebo rozhodnutí.
    assert set(calls) <= {"/api/process", "/api/agent/bridge-one"}


def test_bridge_detail_exposes_public_telemetry_not_raw_reasoning():
    def fetch(path):
        if path == "/api/process":
            return 200, {"runs": [{"run": "safe-run", "bridge_run_ids": ["bridge-one"]}]}
        assert path == "/api/agent/bridge-one"
        return 200, {"state": {"value": "RUNNING", "at": "2026-09-10T10:00:00Z"},
            "context": {"input_tokens": 123, "context_window": 200000, "source": "Bridge GET /runs/bridge-one", "at": "source-time"},
            "costs": {"actual_usd": 1.5, "estimated_usd": 2.0, "source": "Bridge GET /runs/bridge-one", "at": "source-time"},
            "model": {"name": "sonnet", "provider": "anthropic"}, "usage_available": True,
            "tools": [{"name": "pytest", "args_preview": "password=secret-value", "source": "Bridge worker_event #4"}],
            "thoughts": ["PRIVATE_REASONING"], "raw": {"worker_session": {"session_id": "s-123"}, "worker_messages": ["PRIVATE_MESSAGES"]}}
    detail = agent_sources.OporaProcessSource(fetch=fetch).run_detail("safe-run")
    assert "telemetry" in detail, "Chybí skutečná Bridge telemetrie detailu"
    assert detail["sessionId"] == "s-123"
    assert detail["telemetry"][0]["context"]["input_tokens"] == 123
    assert detail["telemetry"][0]["costs"]["actual_usd"] == 1.5
    assert "PRIVATE_REASONING" not in str(detail) and "PRIVATE_MESSAGES" not in str(detail)
    assert "secret-value" not in str(detail)


def test_application_registers_the_process_source(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from backend.app.factory import create_app
    def fetch(self, path):
        if path == "/api/process":
            return 200, {"runs": [{"run": "app-fixture", "state": "COMPLETED"}]}
        return 200, {"status": "ok", "bridge": {"ok": True}, "running": [], "waiting": []}
    monkeypatch.setattr(agent_sources.PlatnoSource, "_http_fetch", fetch)
    monkeypatch.setenv("OPORA_AGENT_ORCHESTRATOR_ROOT", str(tmp_path / "missing-fixture"))
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1:8740") as client:
        sources = client.get("/api/agents/sources").json()
        assert "oporacc-process" in sources, "Procesní zdroj není zapojený v aplikaci"
        runs = client.get("/api/agents/runs", params={"source": "oporacc-process"}).json()
        assert [item["runId"] for item in runs["items"]] == ["app-fixture"]
