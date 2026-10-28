"""Strážce pravdy: worktree za `main` (lokální Git) a návrh čekající na člověka déle než 24 h; falešný čas."""
import subprocess

import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.strazci import guard_pravda
from backend.canvas.strazci.registry import GuardContext

NOW = 1_800_000_000.0


def sh(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    sh(root, "init", "-q", "-b", "main")
    sh(root, "config", "user.email", "t@example.com")
    sh(root, "config", "user.name", "T")
    sh(root, "commit", "-q", "--allow-empty", "-m", "start")
    sh(root, "branch", "work/w1")
    for index in range(21):
        sh(root, "commit", "-q", "--allow-empty", "-m", f"c{index}")
    return root


def test_behind_count_reads_local_git_and_tolerates_unknown_branch(repo):
    assert guard_pravda.behind_count(repo, "work/w1", "main") == 21
    assert guard_pravda.behind_count(repo, "work/nic", "main") is None


def test_worktree_over_twenty_commits_behind_is_reported():
    tree = lambda behind: {"id": "w1", "branch": "work/w1", "nodeId": "web", "behind": behind, "main": "main"}  # noqa: E731
    assert guard_pravda.worktree_findings([tree(20), tree(None)]) == []
    [item] = guard_pravda.worktree_findings([tree(21)])
    assert item["key"] == "truth:worktree-behind:w1" and item["nodeId"] == "web" and item["workspaceId"] == "w1"
    assert item["data"] == {"behind": 21, "branch": "work/w1"} and "21 commitů za main" in item["message"]


def test_proposal_waiting_over_a_day_is_reported():
    proposal = lambda age: {"workspaceId": "draft", "id": "p1", "kind": "graph-changes", "subject": "Nová sekce",  # noqa: E731
                            "createdAt": NOW - age}
    assert guard_pravda.proposal_findings([proposal(24 * 3600)], NOW) == []
    [item] = guard_pravda.proposal_findings([proposal(30 * 3600)], NOW)
    assert item["key"] == "truth:proposal-stale:draft:p1" and item["rule"] == "truth.proposal-stale"
    assert item["data"] == {"proposalId": "p1", "kind": "změna grafu", "waitingHours": 30}
    assert guard_pravda.proposal_findings([{**proposal(0), "createdAt": None}], NOW) == []


def test_epoch_reads_iso_without_zone_as_utc():
    assert guard_pravda.epoch("2027-01-15T08:00:00") == guard_pravda.epoch("2027-01-15T08:00:00+00:00")
    assert guard_pravda.epoch("nesmysl") is None


def test_run_over_a_fresh_draft_project_is_quiet(tmp_path):
    service = CanvasService(tmp_path / "data")
    try:
        assert guard_pravda.run(GuardContext(service, "draft", NOW)) == []
    finally:
        service.close()
