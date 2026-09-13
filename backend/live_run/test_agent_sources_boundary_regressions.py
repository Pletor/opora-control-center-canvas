"""RED->GREEN regrese na skutečné nálezy z nezávislého review WU-AGENT-OBSERVABILITY.

Každý test cílí na jeden konkrétní, dříve prokázaný nález (viz FIX-HANDOFF.md):
1) realtime cap na 500 řádků events.jsonl nikdy neukázal novější události,
2) chybějící kořen orchestrátoru se hlásil jako available:true,
3) symlink/junction uvnitř lane adresáře mohl ukázat mimo povolený kořen,
4) (žurnál aktivity: zápis přes API zrušen, testy odstraněny),
5) PlatnoSource nevaliduje loopback URL, nechá se přesměrovat a nemá strop velikosti,
6) redakce maskovala číselnou telemetrii a nechávala unikat "sk-proj-" tvar tokenů.
"""

import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient

from backend.live_run.agent_catalog import AgentCatalog
from backend.api.live_run.agent_routes import create_agent_router
from backend.live_run.agent_sources import LocalOrchestratorSource, PlatnoSource, redact
from backend.app.factory import create_app
from backend.canvas.canvas_service import CanvasService

ORIGIN = "http://127.0.0.1:8740"


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


# ---------------------------------------------------------------------------
# 1) P1: realtime cap musí ukazovat nejnovější události, ne prvních 500 navždy.
# ---------------------------------------------------------------------------


def test_events_beyond_old_500_cap_are_counted_and_previewed(tmp_path):
    directory = tmp_path / "agents-sonnet"
    directory.mkdir()
    (directory / "state.json").write_text(json.dumps({"running": False}), encoding="utf-8")
    events = [
        {"type": "assistant", "message": {"content": [{"type": "text", "text": f"EVENT_{i}"}]}}
        for i in range(501)
    ]
    (directory / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    source = LocalOrchestratorSource(tmp_path)
    lane = source.read_lane("agents-sonnet")
    assert lane["lastEventSeq"] == 501, "cursor se musí posunout na skutečný konec souboru, ne zůstat na 500"
    texts = [b["text"] for event in lane["preview"] for b in event["content"] if b["type"] == "text"]
    assert "EVENT_500" in texts, "náhled musí obsahovat nejnovější událost, ne jen prvních 500"
    assert "EVENT_0" not in texts, "náhled je okno posledních N událostí, ne prvních N"
    assert lane["truncated"] is False


# ---------------------------------------------------------------------------
# 2) Chybějící kořen orchestrátoru musí být explicitně nedostupný.
# ---------------------------------------------------------------------------


def test_missing_orchestrator_root_reports_unavailable_not_true(tmp_path):
    orchestrator = LocalOrchestratorSource(tmp_path / "missing")
    catalog = AgentCatalog(orchestrator=orchestrator)
    health = catalog.source_health()["hermes-orchestrator"]
    assert health["available"] is False
    assert health["lanes"] == []


# ---------------------------------------------------------------------------
# 3) Symlink/junction uvnitř lane adresáře nesmí ukázat mimo kořen.
# ---------------------------------------------------------------------------


def _make_symlink_or_skip(link_path, target_path, *, target_is_directory=False):
    try:
        os.symlink(target_path, link_path, target_is_directory=target_is_directory)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation not permitted on this system: {exc}")


def test_state_file_symlink_escaping_root_is_refused(tmp_path):
    root = tmp_path / "orchestrator"
    root.mkdir()
    lane = root / "agents-sonnet"
    lane.mkdir()
    (lane / "events.jsonl").write_text("", encoding="utf-8")
    outside = tmp_path / "outside-secret.json"
    outside.write_text(json.dumps({"secret_marker": "should-not-be-read"}), encoding="utf-8")
    _make_symlink_or_skip(lane / "state.json", outside)
    source = LocalOrchestratorSource(root)
    detail = source.read_lane("agents-sonnet")
    # Adresář sám je platný (available True), ale state.json mimo kořen se odmítne číst,
    # ne aby shodil celý katalog nebo prosákl obsah mimo povolenou hranici.
    assert detail["available"] is True
    assert detail["state"]["available"] is False


def test_events_file_symlink_escaping_root_is_refused(tmp_path):
    root = tmp_path / "orchestrator"
    root.mkdir()
    lane = root / "ample-sonnet"
    lane.mkdir()
    (lane / "state.json").write_text(json.dumps({"running": False}), encoding="utf-8")
    outside = tmp_path / "outside-events.jsonl"
    outside.write_text(json.dumps({"type": "system", "subtype": "leaked"}) + "\n", encoding="utf-8")
    _make_symlink_or_skip(lane / "events.jsonl", outside)
    source = LocalOrchestratorSource(root)
    detail = source.read_lane("ample-sonnet")
    assert detail["available"] is True
    assert detail["lastEventSeq"] == 0
    assert detail["preview"] == []


def test_lane_directory_itself_symlinked_outside_root_is_refused(tmp_path):
    root = tmp_path / "orchestrator"
    root.mkdir()
    outside_dir = tmp_path / "outside-lane"
    outside_dir.mkdir()
    (outside_dir / "state.json").write_text(json.dumps({"secret_marker": "leak"}), encoding="utf-8")
    _make_symlink_or_skip(root / "natural-opus", outside_dir, target_is_directory=True)
    source = LocalOrchestratorSource(root)
    with pytest.raises(ValueError):
        source.read_lane("natural-opus")


# ---------------------------------------------------------------------------
# 5) PlatnoSource: loopback-only, no redirects, response size cap, null shapes.
# ---------------------------------------------------------------------------


def test_platno_source_rejects_non_loopback_url():
    with pytest.raises(ValueError):
        PlatnoSource("http://example.com:8738")


def test_platno_source_rejects_embedded_credentials():
    with pytest.raises(ValueError):
        PlatnoSource("http://user:pass@127.0.0.1:8738")


def test_platno_status_handles_null_running_and_waiting_shapes():
    def fetch(path):
        if path == "/api/status":
            return 200, {"bridge": {"ok": True}, "running": None, "waiting": None, "cost": None, "at": None}
        return None, None

    source = PlatnoSource(fetch=fetch)
    status = source.status()
    assert status["running"] == []
    assert status["waiting"] == []


class _RedirectAndOversizeHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/redirect-me":
            self.send_response(302)
            self.send_header("Location", "http://evil.example.invalid/steal")
            self.end_headers()
        elif self.path == "/oversized":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"[" + b"0" * (2_100_000) + b"]")
        else:
            self.send_response(404)
            self.end_headers()


@pytest.fixture
def loopback_server():
    server = HTTPServer(("127.0.0.1", 0), _RedirectAndOversizeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    thread.join(timeout=5)


def test_platno_source_does_not_follow_redirects(loopback_server):
    port = loopback_server.server_address[1]
    source = PlatnoSource(f"http://127.0.0.1:{port}")
    status, body = source._http_fetch("/redirect-me")
    assert status is None and body is None


def test_platno_source_caps_oversized_response(loopback_server):
    port = loopback_server.server_address[1]
    source = PlatnoSource(f"http://127.0.0.1:{port}")
    status, body = source._http_fetch("/oversized")
    assert status is None and body is None


# ---------------------------------------------------------------------------
# 6) Redakce: číselná telemetrie (token counts) se nemaskuje; sk-proj- token ano.
# ---------------------------------------------------------------------------


def test_redact_preserves_numeric_token_counts():
    value = redact({"input_tokens": 512, "output_tokens": 48, "usage": {"cache_read_input_tokens": 10}})
    assert value["input_tokens"] == 512
    assert value["output_tokens"] == 48
    assert value["usage"]["cache_read_input_tokens"] == 10


def test_redact_still_masks_real_token_credential_key():
    value = redact({"access_token": "abcdef123456", "bearer": "abcdef123456"})
    assert value["access_token"] == "[REDACTED]"
    assert value["bearer"] == "[REDACTED]"


def test_redact_masks_full_sk_proj_style_key_in_text():
    leaked = "leaked key sk-proj-AbCdEfGh12345678_ZyXwVu key"
    value = redact(leaked)
    assert "sk-proj-" not in value
    assert "ZyXwVu" not in value, "zbytek tokenu za pomlčkou nesmí uniknout redakci"


# ---------------------------------------------------------------------------
# 7) HTTP hranice: readOnly main + CAS 409 přes skutečný create_app boundary.
# ---------------------------------------------------------------------------


@pytest.fixture
def git_main_client(tmp_path):
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    git(upstream, "init", "-b", "main")
    git(upstream, "config", "user.name", "Fixture")
    git(upstream, "config", "user.email", "fixture@example.invalid")
    (upstream / "opora-canvas.json").write_text(
        json.dumps({"nodes": [{"id": "n1", "parentId": None, "kind": "node", "name": "n1", "purpose": "", "x": 0, "y": 0}], "edges": []}),
        encoding="utf-8",
    )
    git(upstream, "add", ".")
    git(upstream, "commit", "-m", "initial")
    managed = tmp_path / "data" / "projects" / "fixture" / "main"
    managed.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", str(upstream), str(managed)], check=True, capture_output=True)
    app = create_app(tmp_path / "data")
    service = app.state.service
    project = service.register_repository("fixture", "Fixture", str(managed), "fixture://local", "main")
    # create_app již připojilo statické plátno na catch-all /. Nové API musí
    # dostat přednost stejně jako při integraci před app.mount v app factory.
    from starlette.routing import Mount

    static_routes = [route for route in app.router.routes if isinstance(route, Mount)]
    for route in static_routes:
        app.router.routes.remove(route)
    app.include_router(
        create_agent_router(service, platno_base_url="http://127.0.0.1:8739", orchestrator_root=tmp_path / "no-orchestrator")
    )
    app.router.routes.extend(static_routes)
    with TestClient(app, base_url=ORIGIN) as client:
        yield client, project["id"]


def test_binding_on_main_is_rejected_via_real_boundary(git_main_client):
    client, project_id = git_main_client
    response = client.post(
        "/api/agents/bindings",
        headers={"origin": ORIGIN, "content-type": "application/json"},
        json={
            "project": project_id,
            "workspace": "main",
            "layer": "",
            "nodeId": "n1",
            "sourceId": "hermes-orchestrator",
            "runId": "agents-sonnet",
            "sessionId": None,
            "expectedRevision": 0,
            "confirmed": True,
        },
    )
    assert response.status_code == 409


@pytest.fixture
def draft_client(tmp_path):
    app = create_app(tmp_path / "data")
    service = app.state.service
    # create_app již připojilo statické plátno na catch-all /. Nové API musí
    # dostat přednost stejně jako při integraci před app.mount v app factory.
    from starlette.routing import Mount

    static_routes = [route for route in app.router.routes if isinstance(route, Mount)]
    for route in static_routes:
        app.router.routes.remove(route)
    app.include_router(
        create_agent_router(service, platno_base_url="http://127.0.0.1:8739", orchestrator_root=tmp_path / "no-orchestrator")
    )
    app.router.routes.extend(static_routes)
    with TestClient(app, base_url=ORIGIN) as client:
        headers = {"origin": ORIGIN, "content-type": "application/json"}
        old = client.get("/api/view", params={"project": "draft", "workspace": "draft"}).json()
        graph = {"nodes": [{"id": "n1", "parentId": None, "kind": "node", "name": "n1", "purpose": "", "x": 0, "y": 0}], "edges": []}
        result = client.post(
            "/api/graph",
            headers=headers,
            json={"project": "draft", "workspace": "draft", "graph": graph, "digest": old["digest"]},
        )
        assert result.status_code == 200
        yield client


def test_binding_cas_conflict_is_409_via_real_boundary(draft_client):
    headers = {"origin": ORIGIN, "content-type": "application/json"}
    payload = {
        "project": "draft",
        "workspace": "draft",
        "layer": "",
        "nodeId": "n1",
        "sourceId": "hermes-orchestrator",
        "runId": "agents-sonnet",
        "sessionId": None,
        "expectedRevision": 0,
        "confirmed": True,
    }
    first = draft_client.post("/api/agents/bindings", headers=headers, json=payload)
    assert first.status_code == 200
    stale_again = draft_client.post("/api/agents/bindings", headers=headers, json=payload)
    assert stale_again.status_code == 409
