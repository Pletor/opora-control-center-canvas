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


def test_hook_control_lsp_semantic_and_vscode_routes_are_wired(tmp_path):
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
        # The installer resolves bindings through HookControl; an unknown binding is a 4xx, not a crash.
        assert client.get("/api/agent-hooks/vscode?bindingId=missing").status_code in {404, 409}


def test_unknown_api_path_is_not_found_for_every_method(tmp_path):
    origin = "http://127.0.0.1:8740"
    with TestClient(create_app(tmp_path / "data"), base_url=origin) as client:
        assert client.get("/api/neznama-cesta").status_code == 404
        post = client.post("/api/neznama-cesta", headers={"origin": origin}, json={})
        assert post.status_code == 404
        assert post.json()["error"] == "Neznámá cesta API."
