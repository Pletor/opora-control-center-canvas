"""Skladiště worktree (docs/domeny-a-worktree.md §6, §13.3): přesun s reálným Git repem, odmítnutí, výpis."""

import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from backend.canvas.test_canvas_service import git, managed_fixture
from backend.canvas.test_graph_card import node
from backend.canvas.test_project_architecture import domain, page
from backend.project.architecture.work_status import work_status
from backend.project.worktrees import workspace_archive
from backend.project.worktrees.test_workspace_domain import with_architecture
from backend.project.worktrees.workspace_archive import WorkspaceArchive


@pytest.fixture
def project(tmp_path):
    s, p = managed_fixture(tmp_path)
    pid = p["id"]
    with_architecture(s, pid, domain(), page())
    w = s.create_workspace(pid, "app", "Agent A")
    current = s.view(pid, w["id"])
    graph = {"nodes": [*current["graph"]["nodes"], node("card", parent_id="page")], "edges": []}
    s.save_graph(pid, w["id"], graph, current["digest"], actor="human")
    yield s, pid, w, WorkspaceArchive(s)
    s.close()


def with_lease(monkeypatch, wid, expires_in, activity_age=None):
    """Zdroje stavu práce s jednou lease karty na worktree (a volitelně aktivitou před `activity_age` s)."""
    now = time.time()
    activity = [] if activity_age is None else [{
        "workspace_id": wid, "node_id": "card", "agent": "a",
        "updated_at": datetime.fromtimestamp(now - activity_age, UTC).isoformat()}]
    sources = {"leases": [{"workspace_id": wid, "node_id": "card", "owner": "a", "expires_at": now + expires_in}],
               "activity": activity}
    monkeypatch.setattr(workspace_archive, "collect_sources", lambda _service, _pid: sources)


def request(pid, reason="Nápad nevyšel"):
    return {"project": pid, "reason": reason, "confirmed": True}


def test_archive_keeps_branch_removes_worktree_and_moves_data(project):
    s, pid, w, archive = project
    data = s.graph_file(pid, w["id"]).parent
    assert data.exists()
    result = archive.archive(w["id"], request(pid))
    assert result == {"archived": w["id"], "branch": "work/" + w["id"]}
    repo = s.row("projects", pid)["repo"]
    assert git(repo, "branch", "--list", "work/" + w["id"]).endswith("work/" + w["id"])
    assert not Path(w["directory"]).exists()
    assert Path(w["directory"]).name not in git(repo, "worktree", "list")
    assert not data.exists()
    assert (data.parent / "_archive" / w["id"] / "graph.json").exists()
    with pytest.raises(ValueError, match="nalezena"):
        s.row("workspaces", w["id"])
    items = archive.items(pid)["items"]
    assert [(i["id"], i["nodeId"], i["branch"], i["actor"], i["reason"]) for i in items] == [
        (w["id"], "app", "work/" + w["id"], "Agent A", "Nápad nevyšel")]
    assert items[0]["archivedAt"]


def test_archived_worktree_leaves_view_and_work_status(project):
    s, pid, w, archive = project
    assert [row["id"] for row in s.view(pid, "main")["workspaces"]] == [w["id"]]
    archive.archive(w["id"], request(pid))
    assert s.view(pid, "main")["workspaces"] == []
    status = work_status(s, pid)
    assert status["domains"][0]["worktrees"] == [] and status["unassigned"] == []


def test_archived_worktree_does_not_block_domain_removal_but_is_listed(project):
    s, pid, w, archive = project
    # Obsah worktree (karta) a jeho node_id by odebrání blokovaly; ve skladišti už ne.
    assert s.removals.preview(pid, "main", "node", "app")["blockedBy"]
    archive.archive(w["id"], request(pid))
    preview = s.removals.preview(pid, "main", "node", "app")
    assert preview["blockedBy"] == []
    assert [item["workspace"] for item in preview["archivedWorktrees"]] == [w["id"]]


def test_archive_refuses_dirty_worktree(project):
    s, pid, w, archive = project
    Path(w["directory"], "README.md").write_text("rozdělaná práce")
    with pytest.raises(ValueError, match="neuložené změny"):
        archive.archive(w["id"], request(pid))
    assert Path(w["directory"]).exists() and archive.items(pid)["items"] == []
    assert s.row("workspaces", w["id"])["id"] == w["id"]


@pytest.mark.parametrize("activity_age", [5, None])
def test_archive_refuses_live_lease(project, monkeypatch, activity_age):
    _s, pid, w, archive = project
    with_lease(monkeypatch, w["id"], 600, activity_age)
    with pytest.raises(ValueError, match="pracuje"):
        archive.archive(w["id"], request(pid))
    assert Path(w["directory"]).exists() and archive.items(pid)["items"] == []


def test_archive_allows_stopped_lease(project, monkeypatch):
    _s, pid, w, archive = project
    with_lease(monkeypatch, w["id"], -5, 3600)
    assert archive.archive(w["id"], request(pid))["archived"] == w["id"]


@pytest.mark.parametrize("payload", [
    {"reason": "x", "confirmed": False},
    {"reason": "  ", "confirmed": True},
    {"confirmed": True},
])
def test_archive_needs_confirmation_and_reason(project, payload):
    _s, pid, w, archive = project
    with pytest.raises(ValueError):
        archive.archive(w["id"], {"project": pid, **payload})
    assert Path(w["directory"]).exists()


def test_failed_git_remove_changes_nothing(project, monkeypatch):
    s, pid, w, archive = project
    real = workspace_archive.git

    def failing(root, *args, **kwargs):
        if args[:2] == ("worktree", "remove"):
            raise ValueError("Git operace selhala.")
        return real(root, *args, **kwargs)

    monkeypatch.setattr(workspace_archive, "git", failing)
    with pytest.raises(ValueError, match="Nic se nezměnilo"):
        archive.archive(w["id"], request(pid))
    assert archive.items(pid)["items"] == [] and [r["id"] for r in s.workspaces(pid)] == [w["id"]]


def test_interrupted_archive_finishes_on_retry(project, monkeypatch):
    s, pid, w, archive = project

    def locked(*_args):
        raise OSError("zamčeno")

    monkeypatch.setattr(workspace_archive.shutil, "move", locked)
    with pytest.raises(ValueError, match="Hotovo: záznam ve skladišti, worktree odebrán"):
        archive.archive(w["id"], request(pid))
    # Mezistav: worktree je pryč a ze seznamů zmizel; řádek workspaces drží údaje k dokončení.
    assert s.workspaces(pid) == [] and not Path(w["directory"]).exists()
    monkeypatch.undo()
    assert archive.archive(w["id"], request(pid))["archived"] == w["id"]
    assert (s.graph_file(pid, w["id"]).parent.parent / "_archive" / w["id"]).exists()
    assert len(archive.items(pid)["items"]) == 1
    with pytest.raises(ValueError, match="nalezena"):
        s.row("workspaces", w["id"])
