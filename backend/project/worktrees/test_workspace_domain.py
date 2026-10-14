"""Worktree patří doméně architektury (docs/domeny-a-worktree.md §6): založení a přeřazení."""

import pytest

from backend.canvas.test_canvas_service import managed_fixture
from backend.canvas.test_project_architecture import domain, page
from backend.project.worktrees.workspace_domain import domain_ids, rebind


def with_architecture(s, pid, *nodes):
    graph = {"nodes": list(nodes), "edges": []}
    s.architecture.save({"project": pid, "workspace": "main", "expectedRevision": 0, "graph": graph}, actor="human")


@pytest.fixture
def project(tmp_path):
    s, p = managed_fixture(tmp_path)
    with_architecture(s, p["id"], domain(), domain("dev", host="app.example.dev"), page())
    yield s, p["id"]
    s.close()


def test_domain_ids_are_application_nodes_only():
    assert domain_ids({"nodes": [domain(), page()], "edges": []}) == {"app"}


def test_create_workspace_requires_a_domain(project):
    s, pid = project
    for node_id in ("page", "project", "missing"):
        with pytest.raises(ValueError, match="doméně"):
            s.create_workspace(pid, node_id, "Agent")
    assert s.workspaces(pid) == []
    created = s.create_workspace(pid, "app", "Agent")
    assert created["node_id"] == "app" and created["branch"] == "work/" + created["id"]


def test_rebind_moves_workspace_to_another_domain(project):
    s, pid = project
    legacy = s._add_worktree(pid, "project", "01-start-projektu")  # starý worktree bez domény
    moved = rebind(s, legacy["id"], {"project": pid, "nodeId": "dev"})
    assert moved["node_id"] == "dev" and moved["directory"] == legacy["directory"]
    with pytest.raises(ValueError, match="doméně"):
        rebind(s, legacy["id"], {"project": pid, "nodeId": "page"})
    with pytest.raises(ValueError, match="formát"):
        rebind(s, legacy["id"], {"project": pid})
    assert s.row("workspaces", legacy["id"])["node_id"] == "dev"
