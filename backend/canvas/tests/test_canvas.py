import subprocess
from pathlib import Path

import pytest

from backend.canvas.canvas_service import CanvasService, validate_graph


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def test_empty_draft_persists_and_rejects_stale_update(tmp_path):
    s = CanvasService(tmp_path / "data")
    first = s.view("draft", "draft")
    assert first["graph"]["nodes"] == []
    graph = {
        "nodes": [
            {
                "id": "sector1",
                "parentId": None,
                "kind": "sector",
                "name": "Backend",
                "purpose": "Purpose",
                "x": 0,
                "y": 0,
            }
        ],
        "edges": [],
    }
    updated = s.save_graph("draft", "draft", graph, first["digest"])
    assert CanvasService(tmp_path / "data").view("draft", "draft")["graph"] == graph
    with pytest.raises(ValueError, match="změnilo"):
        s.save_graph("draft", "draft", graph, first["digest"])
    assert updated["digest"] != first["digest"]


def test_graph_rejects_cycles_missing_parents_and_unsafe_values():
    with pytest.raises(ValueError):
        validate_graph(
            {
                "nodes": [
                    {
                        "id": "a",
                        "parentId": "a",
                        "kind": "node",
                        "name": "A",
                        "purpose": "",
                        "x": 0,
                        "y": 0,
                    }
                ],
                "edges": [],
            }
        )
    with pytest.raises(ValueError):
        validate_graph(
            {
                "nodes": [
                    {
                        "id": "a",
                        "parentId": "missing",
                        "kind": "node",
                        "name": "A",
                        "purpose": "",
                        "x": 0,
                        "y": 0,
                    }
                ],
                "edges": [],
            }
        )


def test_two_workspaces_are_isolated_and_main_is_read_only(tmp_path):
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    git(upstream, "init", "-b", "main")
    git(upstream, "config", "user.name", "Fixture")
    git(upstream, "config", "user.email", "fixture@example.invalid")
    (upstream / "README.md").write_text("base")
    git(upstream, "add", ".")
    git(upstream, "commit", "-m", "initial")
    s = CanvasService(tmp_path / "data")
    managed = tmp_path / "data" / "projects" / "fixture" / "main"
    managed.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", str(upstream), str(managed)], check=True, capture_output=True)
    p = s.register_repository("fixture", "Fixture", str(managed), "fixture://local", "main")
    a = s.create_workspace(p["id"], "node1", "Agent A")
    b = s.create_workspace(p["id"], "node2", "Agent B")
    assert a["directory"] != b["directory"]
    Path(a["directory"], "README.md").write_text("agent A")
    assert Path(b["directory"], "README.md").read_text() == "base"
    assert (managed / "README.md").read_text() == "base"
    with pytest.raises(ValueError):
        s.save_graph(p["id"], "main", {"nodes": [], "edges": []}, s.view(p["id"], "main")["digest"])
    assert s.view(p["id"], a["id"])["dirty"] is True
    assert s.view(p["id"], "main")["dirty"] is False
