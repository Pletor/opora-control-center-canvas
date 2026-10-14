"""Cílové repo zůstává čisté: graf Git pracovního prostoru i export zadání leží v datech plátna."""
import json
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.canvas_service import CanvasService
from backend.canvas.graph import encode

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
GRAPH = {"nodes": [
    {"id": "sector", "parentId": None, "kind": "sector", "name": "Backend", "purpose": "Sektor", "x": 0, "y": 0},
    {"id": "card", "parentId": "sector", "kind": "node", "name": "Karta", "purpose": "Úkol", "x": 10, "y": 20},
], "edges": []}


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def repository(tmp_path, data):
    """Spravovaný klon git projektu v datech plátna."""
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    git(upstream, "init", "-b", "main")
    (upstream / "README.md").write_text("base", encoding="utf-8")
    git(upstream, "add", ".")
    git(upstream, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "initial")
    managed = data / "projects" / "fixture" / "main"
    managed.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", str(upstream), str(managed)], check=True, capture_output=True)
    return managed


def workspace(service, managed, legacy=None):
    project = service.register_repository("fixture", "Fixture", str(managed), "fixture://local", "main")["id"]
    created = service.create_workspace(project, "card", "Agent")
    directory = Path(created["directory"])
    if legacy is not None:
        (directory / "opora-canvas.json").write_text(encode(legacy), encoding="utf-8")
    return project, created["id"], directory


def test_git_workspace_graph_is_stored_in_canvas_data_not_in_worktree(tmp_path):
    data = tmp_path / "data"
    service = CanvasService(data)
    project, wid, directory = workspace(service, repository(tmp_path, data))
    first = service.view(project, wid)
    assert first["graphStatus"] == "missing"

    saved = service.save_graph(project, wid, GRAPH, first["digest"])

    stored = service.graph_file(project, wid)
    assert stored == data.resolve() / "projects" / project / "canvas" / "workspaces" / wid / "graph.json"
    assert json.loads(stored.read_text(encoding="utf-8")) == GRAPH
    assert not (directory / "opora-canvas.json").exists()
    assert saved["graph"] == GRAPH and saved["dirty"] is False
    assert git(directory, "status", "--porcelain", "--untracked-files=all") == ""
    # Nová instance (restart serveru) čte graf z dat plátna.
    assert CanvasService(data).view(project, wid)["graph"] == GRAPH


def test_legacy_worktree_graph_is_adopted_once_and_left_untouched(tmp_path):
    data = tmp_path / "data"
    service = CanvasService(data)
    legacy = {"nodes": [GRAPH["nodes"][0]], "edges": []}
    project, wid, directory = workspace(service, repository(tmp_path, data), legacy=legacy)
    legacy_file = directory / "opora-canvas.json"
    legacy_bytes = legacy_file.read_bytes()

    adopted = service.view(project, wid)
    assert adopted["graph"] == legacy and adopted["graphStatus"] == "present"
    assert "Převzatý" in adopted["source"]

    service.save_graph(project, wid, GRAPH, adopted["digest"])

    assert json.loads(service.graph_file(project, wid).read_text(encoding="utf-8")) == GRAPH
    assert legacy_file.read_bytes() == legacy_bytes  # starý soubor se nemaže ani nepřepisuje
    # Po převzetí rozhodují data plátna, ne starý soubor ve worktree.
    legacy_file.write_text(encode({"nodes": [], "edges": []}), encoding="utf-8")
    after = service.view(project, wid)
    assert after["graph"] == GRAPH and after["source"] == "Graf pracovního prostoru v datech plátna"


def test_external_task_export_goes_to_canvas_data_and_keeps_worktree_clean(tmp_path):
    data = tmp_path / "data"
    app = create_app(data)
    service = app.state.service
    project, wid, directory = workspace(service, repository(tmp_path, data))
    scope = {"project": project, "workspace": wid}
    with TestClient(app, base_url=ORIGIN) as client:
        view = client.get("/api/view", params=scope).json()
        saved = client.post("/api/graph", headers=HEADERS, json={**scope, "graph": GRAPH, "digest": view["digest"]})
        assert saved.status_code == 200, saved.text
        spec = client.post("/api/node-spec", headers=HEADERS, json={**scope, "node": "card", "expected_revision": 0,
                           "fields": {"goal": "Cíl", "non_goals": "Nic navíc", "acceptance": "Test prochází"}})
        assert spec.status_code == 200, spec.text
        request = {**scope, "nodeId": "card", "path": "", "sessionId": "", "references": [], "note": ""}
        preview = client.post("/api/desktop-v3/packet/preview", headers=HEADERS, json=request)
        assert preview.status_code == 200, preview.text
        snapshot = client.post("/api/desktop-v3/packet/snapshot", headers=HEADERS,
                               json={**request, "digest": preview.json()["digest"]})
        assert snapshot.status_code == 200, snapshot.text
        snapshot = snapshot.json()
        payload = {**scope, "nodeId": "card", "digest": snapshot["digest"]}
        endpoint = f"/api/desktop-v3/packet/snapshots/{snapshot['id']}/external-export"

        written = client.post(endpoint, headers=HEADERS, json=payload)
        assert written.status_code == 200, written.text
        read = client.get(endpoint, params=payload)
        assert read.status_code == 200, read.text

    expected = data.resolve() / "projects" / project / "packets" / "external-tasks" / wid / "card.md"
    assert written.json()["path"] == read.json()["path"] == str(expected)
    assert expected.read_text(encoding="utf-8") == read.json()["content"]
    assert not (directory / "docs").exists()
    assert git(directory, "status", "--porcelain", "--untracked-files=all") == ""
