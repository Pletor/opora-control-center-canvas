from fastapi.testclient import TestClient

from backend.app.factory import create_app


def test_empty_application_and_origin_gate(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url="http://127.0.0.1:8740") as client:
        r = client.get("/api/bootstrap")
        assert r.status_code == 200 and r.json()["projects"] == []
        assert client.get("/api/view?project=draft&workspace=draft").json()["graph"]["nodes"] == []
        assert (
            client.post(
                "/api/connect",
                json={"url": "https://github.com/x/y", "approved": True},
                headers={"origin": "https://evil.test"},
            ).status_code
            == 403
        )
        assert client.get("/api/bootstrap", headers={"host": "evil.test"}).status_code == 403
        assert (
            client.post(
                "/api/connect",
                json={"url": "https://github.com/x/y", "approved": False},
                headers={"origin": "http://127.0.0.1:8740"},
            ).status_code
            == 409
        )


def test_lsp_and_semantic_routes_are_wired(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url="http://127.0.0.1:8740") as client:
        for path in ("/api/semantic-search/status", "/api/code-intelligence/status"):
            assert client.get(f"{path}?project=draft&workspace=draft").status_code == 200
        assert client.post("/api/semantic-search/query", json={}).status_code != 404
        assert client.post("/api/code-intelligence/query", json={}).status_code != 404
        semantic = client.get("/api/semantic-search/status?project=draft&workspace=draft").json()
        lsp = client.get("/api/code-intelligence/status?project=draft&workspace=draft").json()
        # LSP status mirrors the real semantic service instead of a hardcoded unavailable.
        assert lsp["semantic"]["status"] == semantic["status"]
        assert lsp["semantic"]["reason"] == semantic["detail"]
        assert lsp["preference"] == ["lsp", "semantic", "scoped-text"]


def test_unknown_api_path_is_not_found_for_every_method(tmp_path):
    origin = "http://127.0.0.1:8740"
    with TestClient(create_app(tmp_path / "data"), base_url=origin) as client:
        assert client.get("/api/neznama-cesta").status_code == 404
        post = client.post("/api/neznama-cesta", headers={"origin": origin}, json={})
        assert post.status_code == 404
        assert post.json()["error"] == "Neznámá cesta API."


def test_enabled_heart_runs_only_through_the_flow_engine(tmp_path, monkeypatch):
    monkeypatch.setenv("OPORA_HEART", "on")
    app = create_app(tmp_path / "data")
    with TestClient(app, base_url="http://127.0.0.1:8740") as client:
        assert app.state.flow.thread.is_alive() and len(app.state.flow.hooks) == 1
        assert app.state.flow.wakeup is app.state.heart.wakeup
        heart = [w for w in client.get("/api/flow/workflows").json()["workflows"] if w["kind"] == "heart"]
        assert [(w["name"], w["project_id"], w["active_n"]) for w in heart] == [("Srdce v1", None, 1)]


def test_disabled_heart_leaves_the_engine_without_the_heart_hook(tmp_path):
    app = create_app(tmp_path / "data")  # OPORA_HEART=off (backend/conftest.py)
    with TestClient(app, base_url="http://127.0.0.1:8740"):
        assert app.state.flow.hooks == []


def test_failed_activity_record_still_writes_the_outbox_event(tmp_path, monkeypatch):
    from backend.app import factory

    def broken(*args, **kwargs):
        raise RuntimeError("záznam")

    bridged = []
    monkeypatch.setattr(factory.ActivityLog, "record", broken)
    monkeypatch.setattr(factory, "bridge_activity", lambda *args, **kwargs: bridged.append(kwargs["path"]))
    origin = "http://127.0.0.1:8740"
    with TestClient(factory.create_app(tmp_path / "data"), base_url=origin) as client:
        assert client.post("/api/neznama-cesta", headers={"origin": origin}, json={}).status_code == 404
    assert bridged == ["/api/neznama-cesta"]
