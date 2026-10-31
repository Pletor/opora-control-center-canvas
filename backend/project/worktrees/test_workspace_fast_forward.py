"""Posun worktree za main: jen čistý worktree, který je striktním předkem mainu."""
import subprocess

import pytest

from backend.project.worktrees.workspace_fast_forward import fast_forward


def run(root, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-C", str(root), *args],
                          check=True, capture_output=True, text=True).stdout.strip()


def commit(root, name, text):
    (root / name).write_text(text, encoding="utf-8")
    run(root, "add", name)
    run(root, "commit", "-q", "-m", text)
    return run(root, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    run(main, "init", "-q")
    commit(main, "a.txt", "první")
    work = tmp_path / "work"
    run(main, "worktree", "add", "-q", "-b", "work/x", str(work))
    new = commit(main, "b.txt", "druhý")
    return main, work, new


def test_behind_and_clean_is_moved(repo):
    _, work, new = repo
    assert fast_forward(work, new) == new
    assert run(work, "rev-parse", "HEAD") == new


def test_own_commit_is_untouched(repo):
    _, work, new = repo
    own = commit(work, "c.txt", "vlastní")
    assert fast_forward(work, new) is None
    assert run(work, "rev-parse", "HEAD") == own


def test_dirty_tree_is_untouched(repo):
    _, work, new = repo
    before = run(work, "rev-parse", "HEAD")
    (work / "a.txt").write_text("změna", encoding="utf-8")
    assert fast_forward(work, new) is None
    assert run(work, "rev-parse", "HEAD") == before


def test_equal_and_missing_return_none(repo, tmp_path):
    _, work, new = repo
    assert fast_forward(work, new) == new
    assert fast_forward(work, new) is None
    assert fast_forward(tmp_path / "neexistuje", new) is None
