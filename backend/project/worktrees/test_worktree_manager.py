import os
import subprocess
import sys

import pytest

from backend.integrations.gitio import git
from backend.project.worktrees.worktree_manager import WorktreeManager

ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"}


@pytest.fixture(autouse=True)
def identity(monkeypatch):
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)


def project(tmp_path):
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    git(upstream, "init", "-q", "-b", "main")
    (upstream / "README.md").write_text("hello\n", encoding="utf-8")
    git(upstream, "add", ".")
    git(upstream, "commit", "-q", "-m", "init")
    project_dir = tmp_path / "projects" / "p1"
    project_dir.mkdir(parents=True)
    git(tmp_path, "clone", "-q", str(upstream), str(project_dir / "main"))
    return WorktreeManager(project_dir)


def test_create_from_main_and_metadata(tmp_path):
    manager = project(tmp_path)
    meta = manager.create("wt-a")
    assert meta["branch"] == "opora/wt-a" and meta["base"] == "main"
    assert (manager.path("wt-a") / "README.md").read_text(encoding="utf-8") == "hello\n"
    assert (manager.root / "wt-a.json").is_file()
    assert manager.get("wt-a") == meta and [m["id"] for m in manager.list()] == ["wt-a"]
    assert manager.main_is_clean()
    with pytest.raises(ValueError, match="už existuje"):
        manager.create("wt-a")


def test_fork_from_another_worktree_sees_its_commits(tmp_path):
    manager = project(tmp_path)
    manager.create("wt-a")
    (manager.path("wt-a") / "new.txt").write_text("x", encoding="utf-8")
    git(manager.path("wt-a"), "add", ".")
    git(manager.path("wt-a"), "commit", "-q", "-m", "work")
    fork = manager.create("wt-b", base="wt-a")
    assert fork["baseCommit"] == manager.head("wt-a")
    assert (manager.path("wt-b") / "new.txt").is_file()
    assert not (manager.main / "new.txt").exists()
    assert manager.main_is_clean()


def test_run_check_reports_exit_code_and_tails(tmp_path):
    manager = project(tmp_path)
    manager.create("wt-a")
    ok = manager.run_check("wt-a", [sys.executable, "-c", "print('fine')"])
    assert ok["ok"] is True and ok["exitCode"] == 0 and "fine" in ok["stdoutTail"]
    bad = manager.run_check("wt-a", [sys.executable, "-c", "import sys; sys.stderr.write('boom'); sys.exit(3)"])
    assert bad["ok"] is False and bad["exitCode"] == 3 and "boom" in bad["stderrTail"]
    missing = manager.run_check("wt-a", ["definitely-not-a-command-xyz"])
    assert missing["ok"] is False and "nenalezen" in missing["stderrTail"]
    with pytest.raises(ValueError):
        manager.run_check("wt-a", "echo hi")


def test_remove_with_and_without_branch(tmp_path):
    manager = project(tmp_path)
    manager.create("wt-a")
    manager.create("wt-b")
    manager.remove("wt-a")
    manager.remove("wt-b", keep_branch=True)
    branches = git(manager.main, "branch", "--list", "opora/*")
    assert "opora/wt-a" not in branches and "opora/wt-b" in branches
    assert manager.list() == [] and not manager.path("wt-a").exists()
    with pytest.raises(ValueError, match="neexistuje"):
        manager.get("wt-a")
    assert manager.main_is_clean()


def test_main_is_protected_and_ids_validated(tmp_path):
    manager = project(tmp_path)
    for bad in ("main", "wt-A", "wt-", "../x", "wt-" + "a" * 41):
        with pytest.raises(ValueError):
            manager.path(bad)
    with pytest.raises(ValueError, match="main"):
        manager.remove("main")
    with pytest.raises(ValueError, match="main"):
        manager.run_check("main", ["echo"])
    with pytest.raises(ValueError, match="main"):
        manager.create("main")


def test_main_never_changes_after_all_operations(tmp_path):
    manager = project(tmp_path)
    before = git(manager.main, "rev-parse", "HEAD")
    manager.create("wt-a")
    (manager.path("wt-a") / "f.txt").write_text("1", encoding="utf-8")
    git(manager.path("wt-a"), "add", ".")
    git(manager.path("wt-a"), "commit", "-q", "-m", "c")
    manager.run_check("wt-a", [sys.executable, "-c", "open('g.txt','w').write('2')"])
    manager.remove("wt-a")
    assert git(manager.main, "rev-parse", "HEAD") == before
    assert subprocess.run(["git", "status", "--porcelain"], cwd=manager.main, capture_output=True, text=True, env={**os.environ, **ENV}, check=False).stdout == ""
