import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.agent_routes import create_agent_router
from backend.agent_sources import LocalOrchestratorSource, PlatnoSource, redact
from backend.service import CanvasService


def _fetch_from(table):
    def fetch(path):
        if path not in table:
            return None, None
        return table[path]

    return fetch


def test_platno_status_reports_bridge_unavailable_without_hiding_it():
    source = PlatnoSource(
        fetch=_fetch_from(
            {
                "/api/status": (
                    200,
                    {
                        "bridge": {"ok": False, "workers": [], "error": "bridge_unavailable"},
                        "running": [],
                        "waiting": [],
                        "cost": {"today_usd": 0.0, "limit_usd": 2.0},
                        "at": "2026-09-10T01:01:34.490451+00:00",
                    },
                )
            }
        )
    )
    status = source.status()
    assert status["available"] is True
    assert status["bridgeOk"] is False
    assert status["bridgeError"] == "bridge_unavailable"
    # Nulová cena ze zdroje s nedostupným bridgem se nesmí prezentovat jako fakt.
    assert status["cost"]["todayUsd"] is None
    assert status["cost"]["reliable"] is False


def test_platno_status_source_unreachable_is_explicit():
    source = PlatnoSource(fetch=_fetch_from({}))
    status = source.status()
    assert status["available"] is False
    assert status["bridgeOk"] is False
    assert status["bridgeError"] == "source_unreachable"


def test_platno_projects_parses_real_shape():
    source = PlatnoSource(
        fetch=_fetch_from(
            {
                "/api/platno/projekty": (
                    200,
                    {
                        "projekty": [
                            {
                                "id": "8683e32f08e9460bbac68b3771db6dfa",
                                "nazev": "Ample Lab",
                                "repo_cesta": "I:\\1. Projekty\\ample",
                            }
                        ]
                    },
                )
            }
        )
    )
    projects = source.projects()
    assert projects == [
        {"id": "8683e32f08e9460bbac68b3771db6dfa", "name": "Ample Lab", "repoPath": "I:\\1. Projekty\\ample"}
    ]


def test_redact_masks_secret_keys_and_inline_tokens():
    value = redact({"authorization": "Bearer abcdefghijk", "note": "token=xyz123456 in text"})
    assert value["authorization"] == "[REDACTED]"
    assert "xyz123456" not in value["note"]


def _write_lane(root, lane, *, state, events):
    directory = root / lane
    directory.mkdir(parents=True)
    (directory / "state.json").write_text(json.dumps(state), encoding="utf-8")
    (directory / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")


def test_local_orchestrator_strips_thinking_and_redacts(tmp_path):
    _write_lane(
        tmp_path,
        "agents-sonnet",
        state={"modelAlias": "sonnet", "sessionId": "s1", "running": True, "pid": 111},
        events=[
            {"type": "system", "subtype": "init"},
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "thinking", "thinking": "secret internal plan"},
                        {"type": "text", "text": "Hotovo, token=abcd1234efgh nepatří do UI"},
                    ]
                },
            },
        ],
    )
    source = LocalOrchestratorSource(tmp_path, pid_probe=lambda pid: "process_exists_identity_unconfirmed")
    lane = source.read_lane("agents-sonnet")
    assert lane["available"] is True
    texts = [
        block["text"]
        for event in lane["preview"]
        if event["kind"] == "assistant"
        for block in event["content"]
        if block["type"] == "text"
    ]
    assert texts, "expected at least one text block"
    joined = " ".join(texts)
    assert "secret internal plan" not in joined
    assert "abcd1234efgh" not in joined
    assert lane["liveness"]["status"] == "last_reported_running_liveness_unverified"


def test_local_orchestrator_reports_stale_when_pid_not_running(tmp_path):
    _write_lane(
        tmp_path,
        "ample-sonnet",
        state={"running": True, "pid": 222},
        events=[],
    )
    source = LocalOrchestratorSource(tmp_path, pid_probe=lambda pid: "not_running")
    lane = source.read_lane("ample-sonnet")
    assert lane["liveness"]["status"] == "stale_not_running"


def test_local_orchestrator_missing_lane_is_unknown_not_fabricated(tmp_path):
    source = LocalOrchestratorSource(tmp_path)
    lane = source.read_lane("does-not-exist")
    assert lane["available"] is False
    assert lane["error"] == "source_missing"


def test_local_orchestrator_rejects_path_escape(tmp_path):
    source = LocalOrchestratorSource(tmp_path)
    with pytest.raises(ValueError):
        source.read_lane("../outside")


def test_local_orchestrator_caps_oversized_events_file(tmp_path):
    directory = tmp_path / "big-lane"
    directory.mkdir()
    (directory / "state.json").write_text(json.dumps({"running": False}), encoding="utf-8")
    (directory / "events.jsonl").write_text("x" * (6_000_000), encoding="utf-8")
    source = LocalOrchestratorSource(tmp_path)
    lane = source.read_lane("big-lane")
    assert lane["truncated"] is True
    assert lane["lastEventSeq"] == 0


@pytest.fixture
def agent_app(tmp_path):
    import os

    _write_lane(
        tmp_path / "orchestrator",
        "agents-sonnet",
        state={"modelAlias": "sonnet", "sessionId": "s1", "running": True, "pid": os.getpid()},
        events=[{"type": "system", "subtype": "init"}],
    )
    service = CanvasService(tmp_path / "data")
    app = FastAPI()
    # Neexistující port -> zdroj je záměrně offline pro test.
    app.include_router(
        create_agent_router(
            service,
            platno_base_url="http://127.0.0.1:8739",
            orchestrator_root=tmp_path / "orchestrator",
        )
    )
    with TestClient(app) as client:
        yield client
    service.close()


def test_routes_report_offline_platno_source_explicitly(agent_app):
    body = agent_app.get("/api/agents/sources").json()
    assert body["oporacc-platno"]["available"] is False
    assert body["hermes-orchestrator"]["lanes"] == ["agents-sonnet"]


def test_routes_404_for_unknown_source(agent_app):
    response = agent_app.get("/api/agents/runs/not-a-real-source/whatever")
    assert response.status_code == 404


def test_routes_404_for_path_escape_run_id(agent_app):
    response = agent_app.get("/api/agents/runs/hermes-orchestrator/%2e%2e")
    assert response.status_code == 404


def test_routes_run_detail_strips_thinking_and_marks_brain_unavailable(agent_app):
    body = agent_app.get("/api/agents/runs/hermes-orchestrator/agents-sonnet").json()
    assert body["status"]["liveness"] == "last_reported_running_liveness_unverified"
    assert body["brain"]["contextSnapshot"] == "unavailable"
    assert body["brain"]["verifierArtifact"] == "unavailable"
