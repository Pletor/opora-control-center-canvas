from fastapi.testclient import TestClient

from backend.app.factory import create_app

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
SCOPE = {"project": "draft", "workspace": "draft"}


def node(key, parent=None, kind="node"):
    return {"id": key, "parentId": parent, "kind": kind, "name": key, "purpose": "", "x": 0, "y": 0}


def install_graph(client, graph):
    old = client.get("/api/view", params=SCOPE).json()
    result = client.post(
        "/api/graph", headers=HEADERS, json={**SCOPE, "graph": graph, "digest": old["digest"]}
    )
    assert result.status_code == 200
    return result.json()


def test_remove_one_node_requires_preview_confirmation_and_persists(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        graph = {"nodes": [node("remove"), node("keep")], "edges": []}
        before = install_graph(client, graph)
        params = {**SCOPE, "kind": "node", "target": "remove"}
        preview = client.get("/api/removal-preview", params=params)
        assert preview.status_code == 200
        assert preview.json()["nodeCount"] == 1
        assert client.get("/api/view").json()["digest"] == before["digest"]
        body = {**params, "digest": preview.json()["digest"], "confirmed": True}
        assert (
            client.post(
                "/api/remove", headers=HEADERS, json={**body, "confirmed": False}
            ).status_code
            == 409
        )
        result = client.post("/api/remove", headers=HEADERS, json=body)
        assert result.status_code == 200
        assert [n["id"] for n in result.json()["view"]["graph"]["nodes"]] == ["keep"]
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        assert [n["id"] for n in client.get("/api/view").json()["graph"]["nodes"]] == ["keep"]


def nested_graph():
    return {
        "nodes": [
            node("sector", kind="sector"),
            node("child", "sector"),
            node("deep", "child"),
            node("child2", "sector"),
            node("keep"),
            node("keep2"),
        ],
        "edges": [
            {"id": "outer", "source": "sector", "target": "keep"},
            {"id": "inner", "source": "child", "target": "child2"},
            {"id": "untouched", "source": "keep", "target": "keep2"},
        ],
    }


def test_sector_removes_descendants_and_incident_edges_after_read_only_preview(tmp_path):
    import json

    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        graph = nested_graph()
        install_graph(client, graph)
        changes = app.state.service.db_for("draft").total_changes
        params = {**SCOPE, "kind": "node", "target": "sector"}
        preview = client.get("/api/removal-preview", params=params).json()
        assert preview["nodeCount"] == 4 and preview["edgeCount"] == 2
        assert app.state.service.db_for("draft").total_changes == changes
        result = client.post(
            "/api/remove",
            headers=HEADERS,
            json={**params, "digest": preview["digest"], "confirmed": True},
        )
        assert result.status_code == 200
        assert [n["id"] for n in result.json()["view"]["graph"]["nodes"]] == ["keep", "keep2"]
        assert [e["id"] for e in result.json()["view"]["graph"]["edges"]] == ["untouched"]
        snapshot = app.state.service.db_for("draft").execute("SELECT graph FROM graph_recoveries").fetchone()
        assert json.loads(snapshot[0]) == graph


def test_single_edge_removal_keeps_all_nodes_and_other_edges(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        graph = nested_graph()
        install_graph(client, graph)
        params = {**SCOPE, "kind": "edge", "target": "inner"}
        response = client.get("/api/removal-preview", params=params)
        assert response.status_code == 200
        preview = response.json()
        assert preview["nodeCount"] == 0 and preview["edgeCount"] == 1
        result = client.post(
            "/api/remove",
            headers=HEADERS,
            json={**params, "digest": preview["digest"], "confirmed": True},
        )
        assert result.status_code == 200
        assert result.json()["view"]["graph"]["nodes"] == graph["nodes"]
        assert [e["id"] for e in result.json()["view"]["graph"]["edges"]] == ["outer", "untouched"]


def test_changed_graph_and_rebound_target_reject_old_confirmation(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        graph = nested_graph()
        install_graph(client, graph)
        params = {**SCOPE, "kind": "node", "target": "sector"}
        preview = client.get("/api/removal-preview", params=params).json()
        body = {**params, "digest": preview["digest"], "confirmed": True}
        assert (
            client.post("/api/remove", headers=HEADERS, json={**body, "target": "keep"}).status_code
            == 409
        )
        graph["nodes"][0]["purpose"] = "Změněno v jiném okně"
        install_graph(client, graph)
        assert client.post("/api/remove", headers=HEADERS, json=body).status_code == 409
        assert client.get("/api/view").json()["graph"] == graph


def register_offline_project(service, tmp_path, pid="p"):
    repo = tmp_path / pid
    repo.mkdir()
    (repo / "keep.txt").write_text("nezahodit pracovní data", encoding="utf-8")
    service.register_repository(pid, pid, repo, f"https://github.com/example/{pid}", "main")
    return repo


def test_project_disconnect_hides_registry_but_preserves_files_and_history(tmp_path):
    app = create_app(tmp_path / "data")
    repo = register_offline_project(app.state.service, tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        params = {"project": "p", "workspace": "main", "kind": "project", "target": "p"}
        response = client.get("/api/removal-preview", params=params)
        assert response.status_code == 200
        preview = response.json()
        assert preview["workspaceCount"] == 0
        assert len(client.get("/api/bootstrap").json()["projects"]) == 1
        result = client.post(
            "/api/remove",
            headers=HEADERS,
            json={**params, "digest": preview["digest"], "confirmed": True},
        )
        assert result.status_code == 200
        assert client.get("/api/bootstrap").json()["projects"] == []
        assert (repo / "keep.txt").read_text(encoding="utf-8") == "nezahodit pracovní data"
        assert app.state.service.db.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 1
        assert (
            client.get("/api/view", params={"project": "p", "workspace": "main"}).status_code == 409
        )
        assert (
            client.post(
                "/api/sync", headers=HEADERS, json={"project": "p", "confirmed": True}
            ).status_code
            == 409
        )
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        assert client.get("/api/bootstrap").json()["projects"] == []


def test_project_disconnect_rejects_changed_workspace_set_and_active_job(tmp_path):
    app = create_app(tmp_path / "data")
    service = app.state.service
    register_offline_project(service, tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        params = {"project": "p", "workspace": "main", "kind": "project", "target": "p"}
        result = client.get("/api/removal-preview", params=params)
        assert result.status_code == 200
        body = {**params, "digest": result.json()["digest"], "confirmed": True}
        service.db.execute(
            "INSERT INTO workspaces VALUES(?,?,?,?,?,?,?)",
            ("new", "p", str(tmp_path / "w"), "work/new", "node1", "Fixture", "sha"),
        )
        service.db.commit()
        assert client.post("/api/remove", headers=HEADERS, json=body).status_code == 409
        result = client.get("/api/removal-preview", params=params).json()
        service.db.execute(
            "INSERT INTO jobs VALUES(?,?,?,?,?,?)", ("job", "sync", "queued", "", "p", "now")
        )
        service.db.commit()
        assert (
            client.post(
                "/api/remove", headers=HEADERS, json={**body, "digest": result["digest"]}
            ).status_code
            == 409
        )
        service.db.execute("UPDATE jobs SET status='complete'")
        service.db.commit()
        preview = client.get("/api/removal-preview", params=params).json()
        assert (
            client.post(
                "/api/remove", headers=HEADERS, json={**body, "digest": preview["digest"]}
            ).status_code
            == 200
        )
        assert client.get("/api/bootstrap").json()["jobs"] == []
        import pytest

        with pytest.raises(ValueError):
            service.job("sync", lambda: "p", "p")


def test_generic_graph_write_cannot_bypass_confirmed_deletion(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        current = install_graph(client, {"nodes": [node("protected")], "edges": []})
        response = client.post(
            "/api/graph",
            headers=HEADERS,
            json={**SCOPE, "graph": {"nodes": [], "edges": []}, "digest": current["digest"]},
        )
        assert response.status_code == 409
        assert client.get("/api/view").json()["digest"] == current["digest"]


def test_snapshot_failure_and_missing_origin_leave_graph_unchanged(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        current = install_graph(client, {"nodes": [node("protected")], "edges": []})
        params = {**SCOPE, "kind": "node", "target": "protected"}
        preview = client.get("/api/removal-preview", params=params).json()
        body = {**params, "digest": preview["digest"], "confirmed": True}
        assert client.post("/api/remove", json=body).status_code == 403
        app.state.service.db_for("draft").execute(
            "CREATE TRIGGER fail_snapshot BEFORE INSERT ON graph_recoveries BEGIN SELECT RAISE(ABORT, 'internal-sentinel'); END"
        )
        app.state.service.db_for("draft").commit()
        result = client.post("/api/remove", headers=HEADERS, json=body)
        assert result.status_code == 503 and "internal-sentinel" not in result.text
        assert client.get("/api/view").json()["digest"] == current["digest"]


def test_main_and_other_workspaces_remain_unchanged(tmp_path):
    import json
    import subprocess

    repo = tmp_path / "git"
    repo.mkdir()

    def git(*args):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    git("init", "-b", "main")
    graph = nested_graph()
    source = repo / "opora-canvas.json"
    source.write_text(json.dumps(graph), encoding="utf-8")
    original = source.read_bytes()
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
    service.register_repository("p", "P", repo, "https://github.com/example/p", "main")
    a = service.create_workspace("p", "sector", "A")["id"]
    b = service.create_workspace("p", "sector", "B")["id"]
    with TestClient(app, base_url=ORIGIN) as client:
        main = {"project": "p", "workspace": "main", "kind": "node", "target": "sector"}
        assert client.get("/api/removal-preview", params=main).status_code == 409
        assert (
            client.post(
                "/api/remove",
                headers=HEADERS,
                json={**main, "digest": "invalid", "confirmed": True},
            ).status_code
            == 409
        )
        params = {**main, "workspace": a}
        preview = client.get("/api/removal-preview", params=params).json()
        body = {**params, "digest": preview["digest"], "confirmed": True}
        assert (
            client.post("/api/remove", headers=HEADERS, json={**body, "workspace": b}).status_code
            == 409
        )
        assert client.post("/api/remove", headers=HEADERS, json=body).status_code == 200
        assert (
            client.get("/api/view", params={"project": "p", "workspace": b}).json()["graph"]
            == graph
        )
        assert source.read_bytes() == original
