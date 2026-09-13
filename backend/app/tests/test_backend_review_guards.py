"""RED->GREEN regrese na konkrétní nálezy backendového review WU-DESKTOP-V2.

Každý test cílí na jeden prokázaný nález (viz API-FIX-HANDOFF.md):
1) redaktor kontextových paketů propouštěl holé fine-grained tokeny github_pat_,
2) jediný neplatný název lane (".tmp") shodil celý katalog běhů na 409,
3) dokumentace uložené cesty se stala nečitelnou (503), když zdrojový soubor zmizel,
4) nadměrný events.jsonl se tvářil jako prázdný log (count 0, {}),
5) telemetrie ořezávala text před redakcí a redakce maskovala číselné čítače tokenů.
"""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.project.workspace.tests.test_workspace_sources import ORIGIN, attach

from backend.live_run.agent_catalog import AgentCatalog
from backend.api.live_run.agent_routes import create_agent_router
from backend.live_run.agent_sources import LocalOrchestratorSource, redact
from backend.live_run.agent_telemetry import read_telemetry
from backend.app.factory import create_app
from backend.editor.agent_packet.redact import redact_text
from backend.canvas.canvas_service import CanvasService

# Syntetický token ve tvaru fine-grained GitHub PAT; není to skutečný přístupový údaj.
FIXTURE_PAT = "github_pat_11FAKE0000fakefakefakefake0123456789abcdefghijklmnop"

DOC_FIELDS = {
    "purpose": "Smysl souboru", "goal": "Cíl", "architecture": "Vrstvy",
    "technologies": "Python", "notes": "Poznámky", "requirements": "Požadavek není důkaz.",
}


# ---------------------------------------------------------------------------
# 1) Kontextový paket nesmí propustit holý github_pat_ token do žádné vrstvy.
# ---------------------------------------------------------------------------


def test_packet_redactor_masks_bare_fine_grained_github_token(tmp_path):
    for text in (f"Uzel {FIXTURE_PAT}", f"Účel {FIXTURE_PAT}", f"Deník s tokenem {FIXTURE_PAT}"):
        redacted = redact_text(text)
        assert FIXTURE_PAT not in redacted
        assert "[REDACTED]" in redacted
    assert redact_text("") == "" and redact_text(None) is None
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        view = client.get("/api/view").json()
        nodes = [
            {"id": "sector", "parentId": None, "kind": "sector", "name": "Sektor", "purpose": "", "x": 0, "y": 0},
            {"id": "focus", "parentId": "sector", "kind": "node",
             "name": f"Uzel {FIXTURE_PAT}", "purpose": f"Účel {FIXTURE_PAT}", "x": 0, "y": 0},
        ]
        assert client.post("/api/graph", headers={"origin": ORIGIN}, json={
            "project": "draft", "workspace": "draft", "digest": view["digest"], "graph": {"nodes": nodes, "edges": []},
        }).status_code == 200
        preview = client.post("/api/desktop-v3/packet/preview", headers={"origin": ORIGIN}, json={
            "project": "draft", "workspace": "draft", "nodeId": "focus", "path": "", "sessionId": "",
            "references": [], "note": f"Poznámka {FIXTURE_PAT}",
        })
        assert preview.status_code == 200, preview.text
        assert FIXTURE_PAT not in preview.text
        assert "[REDACTED]" in preview.text


def test_redact_keeps_intentional_numeric_token_counters():
    """Číselné metriky nejsou credentials; canonical cache_read/write_tokens musí přežít."""
    value = redact({
        "input_tokens": 12, "output_tokens": 7,
        "cache_read_tokens": 128, "cache_write_tokens": 64,
        "cacheReadInputTokens": 5, "access_token": "abc123",
    })
    assert value["input_tokens"] == 12 and value["output_tokens"] == 7
    assert value["cache_read_tokens"] == 128 and value["cache_write_tokens"] == 64
    assert value["cacheReadInputTokens"] == 5
    assert value["access_token"] == "[REDACTED]"


# ---------------------------------------------------------------------------
# 2) Jeden neplatný název lane nesmí shodit výpis běhů ostatních zdrojů.
# ---------------------------------------------------------------------------


def _write_lane(root, lane, state, events):
    directory = root / lane
    directory.mkdir(parents=True)
    (directory / "state.json").write_text(json.dumps(state), encoding="utf-8")
    (directory / "events.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
    )
    return directory


def _orchestrator_root_with_stray_dirs(tmp_path):
    root = tmp_path / "orchestrator"
    _write_lane(root, "agents-sonnet", {"running": False, "sessionId": "s1"}, [{"type": "system"}])
    (root / ".tmp").mkdir()
    (root / "lane with space").mkdir()
    (root / ("x" * 80)).mkdir()
    return root


def test_stray_directories_do_not_blank_the_run_catalog(tmp_path):
    root = _orchestrator_root_with_stray_dirs(tmp_path)
    source = LocalOrchestratorSource(root)
    assert source.list_lanes() == ["agents-sonnet"]
    catalog = AgentCatalog(orchestrator=source)
    runs = catalog.list_runs()
    assert [run["runId"] for run in runs["items"]] == ["agents-sonnet"]
    assert catalog.source_health()["hermes-orchestrator"]["lanes"] == ["agents-sonnet"]


def test_api_runs_stay_200_with_invalid_lane_directories(tmp_path):
    root = _orchestrator_root_with_stray_dirs(tmp_path)
    service = CanvasService(tmp_path / "data")
    app = FastAPI()
    # Neexistující port -> platno/process zdroj je záměrně offline.
    app.include_router(create_agent_router(service, platno_base_url="http://127.0.0.1:8739",
                                           orchestrator_root=root))
    try:
        with TestClient(app) as client:
            response = client.get("/api/agents/runs")
            assert response.status_code == 200
            items = response.json()["items"]
            assert [run["runId"] for run in items] == ["agents-sonnet"]
            assert all(run["status"]["reported"] != "unknown" for run in items)
            sources = client.get("/api/agents/sources")
            assert sources.status_code == 200
            assert sources.json()["hermes-orchestrator"]["available"] is True
    finally:
        service.close()


def test_lane_that_disappears_between_listing_and_read_is_skipped(tmp_path):
    root = tmp_path / "orchestrator"
    _write_lane(root, "agents-sonnet", {"running": False}, [{"type": "system"}])

    class Vanishing(LocalOrchestratorSource):
        def list_lanes(self):
            return [*super().list_lanes(), "vanished-lane"]

    catalog = AgentCatalog(orchestrator=Vanishing(root))
    runs = catalog.list_runs()
    assert [run["runId"] for run in runs["items"]] == ["agents-sonnet"]


# ---------------------------------------------------------------------------
# 3) Dokumentace zůstává čitelná i bez zdrojového souboru; nová cesta je 409.
# ---------------------------------------------------------------------------


def test_saved_documentation_survives_deletion_of_its_source_file(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    code = source / "hello.py"
    code.write_text("print('hi')", encoding="utf-8")
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        scope = {"project": pid, "workspace": "draft", "path": "hello.py"}
        saved = client.post("/api/workspace/document", headers={"origin": ORIGIN},
                            json={**scope, "expectedRevision": 0, "fields": DOC_FIELDS, "nodeId": None})
        assert saved.status_code == 200 and saved.json()["revision"] == 1
        code.unlink()
        response = client.get("/api/workspace/document", params=scope)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "source_missing"
        assert body["changeDetection"] == "source_missing"
        assert body["revision"] == 1 and body["fields"] == DOC_FIELDS
        assert set(body) == set(saved.json())


def test_documentation_for_never_existing_path_is_rejected_as_conflict(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "hello.py").write_text("print('hi')", encoding="utf-8")
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        scope = {"project": pid, "workspace": "draft", "path": "nikdy-neexistoval.py"}
        assert client.get("/api/workspace/document", params=scope).status_code == 409
        created = client.post("/api/workspace/document", headers={"origin": ORIGIN},
                              json={**scope, "expectedRevision": 0, "fields": DOC_FIELDS, "nodeId": None})
        assert created.status_code == 409
        escape = {"project": pid, "workspace": "draft", "path": "../mimo.py"}
        assert client.get("/api/workspace/document", params=escape).status_code == 409


def test_documentation_stays_readable_when_whole_source_root_disappears(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    code = source / "hello.py"
    code.write_text("print('hi')", encoding="utf-8")
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        scope = {"project": pid, "workspace": "draft", "path": "hello.py"}
        assert client.post("/api/workspace/document", headers={"origin": ORIGIN},
                           json={**scope, "expectedRevision": 0, "fields": DOC_FIELDS,
                                 "nodeId": None}).status_code == 200
        code.unlink()
        source.rmdir()
        response = client.get("/api/workspace/document", params=scope)
        assert response.status_code == 200
        assert response.json()["status"] == "source_missing"
        assert response.json()["fields"] == DOC_FIELDS


# ---------------------------------------------------------------------------
# 4) Nadměrný events.jsonl je explicitně nedostupný, ne "prázdný log".
# ---------------------------------------------------------------------------


def test_oversized_events_file_reports_unknown_count_not_zero(tmp_path):
    root = tmp_path / "orchestrator"
    directory = root / "big-lane"
    directory.mkdir(parents=True)
    (directory / "state.json").write_text(json.dumps({"running": False}), encoding="utf-8")
    with (directory / "events.jsonl").open("w", encoding="utf-8") as handle:
        line = json.dumps({"type": "system", "subtype": "init"}) + "\n"
        for _ in range(6_000_000 // len(line) + 1):
            handle.write(line)
    assert (directory / "events.jsonl").stat().st_size > 5_000_000
    source = LocalOrchestratorSource(root)
    lane = source.read_lane("big-lane")
    assert lane["available"] is True
    assert lane["lastEventSeq"] is None
    assert lane["eventsStatus"] == "too_large"
    assert lane["eventsReason"] == "events_file_exceeds_max_file_bytes"
    assert lane["truncated"] is True
    catalog = AgentCatalog(orchestrator=source)
    run = catalog.list_runs()["items"][0]
    assert run["runId"] == "big-lane"
    assert run["lastEventSeq"] is None
    assert run["eventsStatus"] == "too_large"
    assert "events" in run["missing"]


# ---------------------------------------------------------------------------
# 5) Telemetrie redakuje před ořezem, ne po něm.
# ---------------------------------------------------------------------------


def test_telemetry_redacts_before_clipping_boundary_token():
    secret_body = "11BOUNDARY0000fakefakefakefake0123456789"
    padded = "a" * 980 + "github_pat_" + secret_body

    def fetch(path):
        assert path == "/api/agent/run-1"
        return 200, {"state": {"value": padded, "current_step": "x"},
                     "raw": {"worker_session": {"session_id": "s1", "parent_session_id": None}}}

    telemetry = read_telemetry(fetch, "http://127.0.0.1:8739", "run-1")
    assert telemetry["available"] is True
    value = telemetry["state"]["value"]
    assert "github_pat_" not in value
    assert secret_body[:8] not in value
    assert len(value) <= 1001


@pytest.mark.parametrize("offset", [0, 970, 985, 995])
def test_telemetry_never_leaks_partial_token_at_any_clip_offset(offset):
    secret = "github_pat_11PARTIAL0000fakefakefakefake01234567"

    def fetch(_path):
        return 200, {"state": {"value": "b" * offset + secret},
                     "raw": {"worker_session": {}}}

    value = read_telemetry(fetch, "http://127.0.0.1:8739", "run-1")["state"]["value"]
    assert "github_pat_" not in value
    assert "11PARTIAL" not in value
