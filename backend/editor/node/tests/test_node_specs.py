import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
NODE = {
    "id": "node-1",
    "parentId": None,
    "kind": "node",
    "name": "Editor",
    "purpose": "Původní podstata",
    "x": 0,
    "y": 0,
}
FIELDS = {
    "goal": "Připravit zadání bez přepisování",
    "non_goals": "Nespouštět agenta",
    "acceptance": "Reload zachová text",
}
SCOPE = {"project": "draft", "workspace": "draft", "node": "node-1"}


def create_node(client):
    view = client.get("/api/view").json()
    result = client.post(
        "/api/graph",
        headers=HEADERS,
        json={
            "project": "draft",
            "workspace": "draft",
            "graph": {"nodes": [NODE], "edges": []},
            "digest": view["digest"],
        },
    )
    assert result.status_code == 200


def test_spec_persists_across_application_restart_without_changing_graph(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        create_node(client)
        before = client.get("/api/view").json()["digest"]
        empty = client.get("/api/node-spec", params=SCOPE)
        assert empty.status_code == 200
        assert empty.json()["revision"] == 0
        saved = client.post(
            "/api/node-spec",
            headers=HEADERS,
            json={**SCOPE, "expected_revision": 0, "fields": FIELDS},
        )
        assert saved.status_code == 200
        assert saved.json()["revision"] == 1
        assert client.get("/api/view").json()["digest"] == before
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        restored = client.get("/api/node-spec", params=SCOPE).json()
        assert restored["fields"] == FIELDS
        assert restored["revision"] == 1
        assert client.get("/api/view").json()["graph"]["nodes"][0]["purpose"] == NODE["purpose"]


def test_stale_save_is_rejected_and_history_preserved(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        create_node(client)
        payload = {**SCOPE, "expected_revision": 0, "fields": FIELDS}
        assert client.post("/api/node-spec", headers=HEADERS, json=payload).status_code == 200
        assert (
            client.post(
                "/api/node-spec",
                headers=HEADERS,
                json={**payload, "fields": {**FIELDS, "goal": "Stará změna"}},
            ).status_code
            == 409
        )
        newer = {**FIELDS, "goal": "Novější zadání"}
        assert (
            client.post(
                "/api/node-spec",
                headers=HEADERS,
                json={**payload, "expected_revision": 1, "fields": newer},
            ).status_code
            == 200
        )
        history = client.get("/api/node-spec/history", params=SCOPE)
        assert history.status_code == 200
        assert [i["revision"] for i in history.json()["items"]] == [2, 1]
        assert history.json()["items"][1]["fields"] == FIELDS
        assert history.json()["has_more"] is False


@pytest.mark.parametrize(
    "change",
    [
        {"expected_revision": False},
        {"expected_revision": "0"},
        {"extra": "ignored?"},
        {"fields": {**FIELDS, "extra": "bad"}},
        {"fields": {"goal": "missing fields"}},
        {"fields": {**FIELDS, "goal": 7}},
        {"fields": {**FIELDS, "goal": "x" * 4001}},
        {"fields": {**FIELDS, "non_goals": "x" * 8001}},
        {"fields": {**FIELDS, "acceptance": "x" * 12001}},
        {"fields": {**FIELDS, "goal": "nul\0character"}},
    ],
)
def test_invalid_spec_payload_does_not_create_revision(tmp_path, change):
    with TestClient(create_app(tmp_path), base_url=ORIGIN, raise_server_exceptions=False) as client:
        create_node(client)
        result = client.post(
            "/api/node-spec",
            headers=HEADERS,
            json={**SCOPE, "expected_revision": 0, "fields": FIELDS, **change},
        )
        assert result.status_code == 409
        assert client.get("/api/node-spec", params=SCOPE).json()["revision"] == 0


def test_two_connections_cannot_both_commit_same_revision(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    with (
        TestClient(create_app(tmp_path), base_url=ORIGIN) as first,
        TestClient(create_app(tmp_path), base_url=ORIGIN) as second,
    ):
        create_node(first)
        payload = {**SCOPE, "expected_revision": 0, "fields": FIELDS}
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    lambda c: c.post("/api/node-spec", headers=HEADERS, json=payload).status_code,
                    [first, second],
                )
            )
        assert sorted(results) == [200, 409]
        assert len(first.get("/api/node-spec/history", params=SCOPE).json()["items"]) == 1


def test_unknown_node_origin_and_main_scope_are_rejected(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        create_node(client)
        payload = {**SCOPE, "expected_revision": 0, "fields": FIELDS}
        assert client.post("/api/node-spec", json=payload).status_code == 403
        assert (
            client.post(
                "/api/node-spec", headers=HEADERS, json={**payload, "node": "unknown"}
            ).status_code
            == 409
        )
        assert (
            client.post(
                "/api/node-spec", headers=HEADERS, json={**payload, "workspace": "main"}
            ).status_code
            == 409
        )


def test_managed_workspace_and_main_history_keep_project_scope(tmp_path):
    import json
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    git("init", "-b", "main")
    (repo / "opora-canvas.json").write_text(
        json.dumps({"nodes": [NODE], "edges": []}), encoding="utf-8"
    )
    git("add", ".")
    git(
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-m",
        "Fixture",
    )
    app = create_app(tmp_path / "data")
    service = app.state.service
    service.register_repository("p", "Project", repo, "https://github.com/example/project", "main")
    service.register_repository("other", "Other", repo, "https://github.com/example/other", "main")
    workspace = service.create_workspace("p", "node-1", "Test")
    with TestClient(app, base_url=ORIGIN) as client:
        scope = {**SCOPE, "project": "p", "workspace": workspace["id"]}
        payload = {**scope, "expected_revision": 0, "fields": FIELDS}
        assert client.post("/api/node-spec", headers=HEADERS, json=payload).status_code == 200
        assert client.get("/api/node-spec", params=scope).json()["fields"] == FIELDS
        assert client.get("/api/node-spec", params={**scope, "project": "other"}).status_code == 409
        assert (
            client.post(
                "/api/node-spec", headers=HEADERS, json={**payload, "project": "other"}
            ).status_code
            == 409
        )
        main = {**scope, "workspace": "main"}
        assert (
            client.post(
                "/api/node-spec", headers=HEADERS, json={**payload, "workspace": "main"}
            ).status_code
            == 409
        )
        value = client.get("/api/node-spec", params=main).json()
        assert value["readOnly"] is True and value["available"] is False
        assert client.get("/api/node-spec/history", params=main).json()["items"] == []


def test_database_failure_is_safe_and_does_not_create_revision(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN, raise_server_exceptions=False) as client:
        create_node(client)
        app.state.service.db.execute(
            "CREATE TRIGGER fail_spec BEFORE INSERT ON node_spec_revisions BEGIN SELECT RAISE(ABORT, 'private-sentinel'); END"
        )
        app.state.service.db.commit()
        result = client.post(
            "/api/node-spec",
            headers=HEADERS,
            json={**SCOPE, "expected_revision": 0, "fields": FIELDS},
        )
        assert result.status_code == 503
        assert "private-sentinel" not in result.text
        assert isinstance(result.json()["error"], str)
        assert client.get("/api/node-spec", params=SCOPE).json()["revision"] == 0


def test_configured_test_port_isolated_from_production(tmp_path, monkeypatch):
    monkeypatch.setenv("OPORA_CANVAS_PORT", "8741")
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1:8741") as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/health", headers={"host": "127.0.0.1:8740"}).status_code == 403
