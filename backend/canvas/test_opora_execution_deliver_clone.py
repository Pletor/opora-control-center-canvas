"""Deliver vidí commit karty pushnutý na origin a čitelně odmítne commit, který je jen u agenta (OP-857D80)."""
import subprocess
from types import SimpleNamespace

import pytest

from backend.app import error_log
from backend.canvas import opora_execution_deliver as deliver_module
from backend.canvas.payload_errors import InvalidPayload


def git(root, *args):
    return subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@example.invalid", "-C", str(root), *args],
                          check=True, capture_output=True, text=True).stdout.strip()


def commit(root, name):
    (root / name).write_text(name)
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", name)
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def repos(tmp_path):
    origin, agent, clone = tmp_path / "origin.git", tmp_path / "agent", tmp_path / "clone"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    git(tmp_path, "clone", "-q", str(origin), str(agent))
    commit(agent, "base.txt")
    git(agent, "push", "-q", "origin", "main")
    git(tmp_path, "clone", "-q", str(origin), str(clone))
    row = {"repo": str(clone), "url": str(origin), "branch": "main"}
    service = SimpleNamespace(row=lambda table, pid: row,
                              project_hub=SimpleNamespace(source_info=lambda project: {"sourceKind": "git"}))
    return agent, clone, service


def test_commit_pushed_after_clone_is_found_by_pulling_clone(repos):
    agent, clone, service = repos
    sha = commit(agent, "karta.txt")
    git(agent, "push", "-q", "origin", "main")
    deliver_module.see_commit(service, "P", "card", str(clone), sha)
    assert git(clone, "rev-parse", "HEAD") == sha


def test_commit_only_in_agent_checkout_is_422_with_push_lever_and_logged(repos, monkeypatch):
    agent, clone, service = repos
    sha = commit(agent, "jen-lokalne.txt")
    logged = []
    monkeypatch.setattr(error_log, "submit", lambda *args, **kwargs: logged.append((args, kwargs)))
    with pytest.raises(InvalidPayload) as refused:
        deliver_module.see_commit(service, "P", "card", str(clone), sha)
    assert "pushni větev s commitem na origin" in str(refused.value.body())
    assert logged[0][0][:2] == ("card", "blocked") and logged[0][1]["subject"] == "card"


def test_local_project_is_not_pulled(repos):
    service = repos[2]
    service.project_hub = SimpleNamespace(source_info=lambda project: {"sourceKind": "local"})
    assert deliver_module.refresh_clone(service, "P") == deliver_module.NO_CLONE
