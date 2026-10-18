"""Posun karet bez celého grafu (`save_positions`, oprava 8 v docs/navrhy/2026-10-14-vykon-platna.md).

Mění jen x/y uvedených uzlů, neznámé ID a chybné pozice odmítne a jde přes `save_graph`, takže na
čistém mainu projde jen posun architektury (domény, stránky), posun obsahu ne.
"""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.canvas_service import CanvasService
from backend.canvas.test_canvas_service import git, managed_fixture
from backend.canvas.test_graph_card import node
from backend.canvas.test_project_architecture import domain, page


@pytest.fixture
def service(tmp_path):
    s = CanvasService(tmp_path / "data")
    s.save_graph("draft", "draft", {"nodes": [node("a"), node("b"), node("s", kind="sector"), node("c", parent_id="s")],
                                    "edges": [{"id": "e1", "source": "a", "target": "b"}]},
                 s.view("draft", "draft")["digest"])
    yield s
    s.close()


def by_id(view):
    return {n["id"]: n for n in view["graph"]["nodes"]}


def test_moves_only_listed_nodes_rounds_and_answers_without_graph(service):
    before = service.view("draft", "draft")
    saved = service.save_positions("draft", "draft", [{"id": "a", "x": 120.6, "y": -40.2}, {"id": "c", "x": 5, "y": 7}],
                                   before["digest"], actor="human")
    assert "graph" not in saved and saved["positions"] == [{"id": "a", "x": 121, "y": -40}, {"id": "c", "x": 5, "y": 7}]
    after = service.view("draft", "draft")
    assert saved["digest"] == after["digest"] != before["digest"]
    nodes, old = by_id(after), by_id(before)
    assert (nodes["a"]["x"], nodes["a"]["y"]) == (121, -40) and (nodes["c"]["x"], nodes["c"]["y"]) == (5, 7)
    for key in ("b", "s"):
        assert nodes[key] == old[key]
    assert {**nodes["a"], "x": 0, "y": 0} == old["a"] and after["graph"]["edges"] == before["graph"]["edges"]


@pytest.mark.parametrize("positions, message", [
    ([{"id": "ghost", "x": 1, "y": 1}], "neexistující"),
    ([{"id": "a", "x": 1, "y": 1}, {"id": "a", "x": 2, "y": 2}], "opakuje"),
    ([{"id": "a", "x": float("nan"), "y": 1}], "konečnými"),
    ([{"id": "a", "x": True, "y": 1}], "konečnými"),
    ([{"id": "a", "x": "1", "y": 1}], "konečnými"),
    ([{"id": "a", "x": 1, "y": 1, "parentId": "s"}], "konečnými"),
    ([], "neprázdný"),
    ({"a": {"x": 1, "y": 1}}, "neprázdný"),
])
def test_invalid_positions_are_rejected_and_nothing_changes(service, positions, message):
    before = service.view("draft", "draft")
    with pytest.raises(ValueError, match=message):
        service.save_positions("draft", "draft", positions, before["digest"])
    assert service.view("draft", "draft")["digest"] == before["digest"]


def test_stale_digest_is_a_conflict(service):
    stale = service.view("draft", "draft")["digest"]
    service.save_positions("draft", "draft", [{"id": "a", "x": 10, "y": 0}], stale)
    with pytest.raises(ValueError, match="změnilo"):
        service.save_positions("draft", "draft", [{"id": "b", "x": 10, "y": 0}], stale)


@pytest.fixture
def git_project(tmp_path):
    s, p = managed_fixture(tmp_path)
    repo = Path(s.row("projects", p["id"])["repo"])
    git(repo, "config", "user.name", "Fixture")
    git(repo, "config", "user.email", "fixture@example.invalid")
    (repo / "opora-canvas.json").write_text(json.dumps({"nodes": [node("loose")], "edges": []}), encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "content on main")
    yield s, p["id"]
    s.close()


def test_clean_main_moves_architecture_but_not_content(git_project):
    s, pid = git_project
    current = s.view(pid, "main")
    s.save_graph(pid, "main", {"nodes": [*current["graph"]["nodes"], domain(), page()], "edges": []},
                 current["digest"], actor="human")
    main = s.view(pid, "main")
    assert main["readOnly"] is True and set(by_id(main)) == {"loose", "app", "page"}
    saved = s.save_positions(pid, "main", [{"id": "page", "x": 400, "y": 80}], main["digest"], actor="human")
    assert saved["architectureRevision"] == main["architectureRevision"] + 1
    assert {n["id"]: (n["x"], n["y"]) for n in s.architecture.read(pid)["graph"]["nodes"]}["page"] == (400, 80)
    with pytest.raises(ValueError, match="pouze pro čtení"):
        s.save_positions(pid, "main", [{"id": "loose", "x": 400, "y": 80}], saved["digest"], actor="human")
    assert (by_id(s.view(pid, "main"))["loose"]["x"]) == 0


def test_route_validates_shape_and_answers_slim(tmp_path):
    origin = "http://127.0.0.1:8740"
    scope = {"project": "draft", "workspace": "draft"}
    with TestClient(create_app(tmp_path), base_url=origin) as client:
        view = client.get("/api/view", params=scope).json()
        graph = {"nodes": [node("a"), node("b")], "edges": []}
        view = client.post("/api/graph", headers={"origin": origin}, json={**scope, "graph": graph, "digest": view["digest"]}).json()
        body = {**scope, "digest": view["digest"], "positions": [{"id": "b", "x": 300, "y": 20}]}
        assert client.post("/api/graph/positions", headers={"origin": origin}, json={**body, "graph": graph}).status_code == 409
        response = client.post("/api/graph/positions", headers={"origin": origin}, json=body)
        assert response.status_code == 200, response.text
        assert "graph" not in response.json() and response.json()["positions"] == [{"id": "b", "x": 300, "y": 20}]
        assert len(response.content) < 2000
        after = client.get("/api/view", params=scope).json()
        assert after["digest"] == response.json()["digest"]
        assert [(n["id"], n["x"], n["y"]) for n in after["graph"]["nodes"]] == [("a", 0, 0), ("b", 300, 20)]
