"""Hlídač gitu srdce (docs/brain-heart-orchestrator.md §4): první průchod jen pamatuje, posun HEAD budí
vstupem `commits` po okně, selhání nebudí, zdroj `git` jde přes existující synchronizaci aplikace."""
import subprocess
from types import SimpleNamespace

import pytest

from backend.brain_opora.determinism import gate_setting
from backend.canvas.canvas_service import CanvasService
from backend.flow.catalogs.heart import git_watch, wakes
from backend.flow.catalogs.heart.conftest import Clock, Runner
from backend.flow.catalogs.heart.heart import Heart

def git(root, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-C", str(root), *args],
                          check=True, capture_output=True, text=True).stdout.strip()


def commit(root, name, subject):
    (root / name).write_text(subject, encoding="utf-8")
    git(root, "add", name)
    git(root, "commit", "-q", "-m", subject)
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def local(tmp_path, make_heart):
    source = tmp_path / "zdroj"
    source.mkdir()
    git(source, "init", "-q")
    commit(source, "a.txt", "První")
    service = CanvasService(tmp_path / "data")
    project = service.project_hub.local_project({"name": "Zdroj", "path": str(source), "confirmed": True})["id"]
    gate_setting.write(service, {"project": project, "enabled": True})
    clock, runner = Clock(), Runner()
    heart, engine = make_heart(service, clock, runner)
    yield service, heart, clock, runner.calls, project, source, engine
    service.close()


def test_first_pass_remembers_then_a_new_commit_wakes_after_the_window(local):
    _, heart, clock, calls, project, source, engine = local
    assert engine.run_once() == [] and heart.status(project)["pending"] == 0  # první průchod jen zapamatuje
    old = heart.heads[(project, "draft")]
    new = commit(source, "b.txt", "Druhý commit")
    clock.now += wakes.GIT_POLL - 1
    assert engine.run_once() == [] and heart.status(project)["pending"] == 0  # hlídač ještě nebyl na řadě
    clock.now += 1
    assert engine.run_once() == [] and heart.status(project)["pending"] == 1  # vstup čeká na okno
    clock.now += wakes.WINDOW + 1
    assert engine.run_once() == [project]
    assert f"NOVÉ COMMITY {old[:7]}..{new[:7]}: {new[:7]} Druhý commit" in calls[0]
    assert len(heart.starts[project]) == 1  # automatický vstup jde do stropu za hodinu


def test_unchanged_head_and_broken_source_do_not_wake(local):
    _, heart, clock, _, project, source, engine = local
    engine.run_once()
    clock.now += wakes.GIT_POLL
    engine.run_once()
    assert heart.status(project)["pending"] == 0
    (source / ".git" / "HEAD").write_text("rozbité", encoding="utf-8")
    clock.now += wakes.GIT_POLL
    assert engine.run_once() == [] and heart.status(project)["pending"] == 0
    assert heart.status(project)["gitError"] and heart.git_busy is False


def test_git_source_runs_the_app_sync_and_a_failed_sync_does_not_wake(local, monkeypatch):
    service, heart, _, _, project, source, engine = local
    monkeypatch.setattr(heart, "_kind", lambda pid: "git")
    monkeypatch.setitem(git_watch.HOME, "git", "draft")  # lokální projekt nemá `main`; zdroj čte `draft`
    monkeypatch.setattr(git_watch, "SYNC_STEP", 0.01)
    synced, fail = [], []

    def sync(pid):  # stejná úloha na pozadí jako `CanvasService.sync`, jen bez fetch
        synced.append(pid)

        def action():
            if fail:
                raise ValueError("Main není čistý.")
            return pid
        return service.job("sync", action, pid)

    monkeypatch.setattr(service, "sync", sync)
    heart.watch_git()
    assert synced == [project] and heart.heads[(project, "draft")] and heart.git_errors == {}
    commit(source, "c.txt", "Po sloučení")
    fail.append(True)
    heart.watch_git()
    assert "Synchronizace selhala" in heart.git_errors[project] and heart.status(project)["pending"] == 0
    fail.clear()
    heart.watch_git()
    assert heart.git_errors == {} and heart.status(project)["pending"] == 1 and synced == [project] * 3


def test_main_of_a_git_source_wakes_the_heart_where_it_works(local):
    _, heart, _, _, project, _, engine = local
    assert heart._targets(project, "main", "git") == ["main"]  # srdce ještě nikde nepracovalo
    heart.tokens[(project, "w1")] = "token"
    assert heart._targets(project, "main", "git") == ["w1"]  # `main` je jen ke čtení, karty vznikají ve w1
    assert heart._targets(project, "w1", "git") == ["w1"] and heart._targets(project, "draft", "local") == ["draft"]


def _bare(monkeypatch, fast_forward):
    """`_advance_one` bez služby: zdroj prostoru je pevná cesta, posun dělá `fast_forward`."""
    monkeypatch.setattr(git_watch, "WorkspaceSources", lambda service: SimpleNamespace(root=lambda p, w: "/tmp/ws"))
    monkeypatch.setattr(git_watch.workspace_fast_forward, "fast_forward", fast_forward)
    heart = Heart.__new__(Heart)
    heart.service, heart.heads = object(), {}
    return heart


def test_advance_one_sets_head_when_moved(monkeypatch):
    heart = _bare(monkeypatch, lambda root, sha: "abc123")
    heart._advance_one("p", "w1", "main-sha")
    assert heart.heads == {("p", "w1"): "abc123"}


def test_advance_one_swallows_exceptions(monkeypatch):
    def boom(root, sha):
        raise RuntimeError("git spadl")

    heart = _bare(monkeypatch, boom)
    heart._advance_one("p", "w1", "main-sha")
    assert heart.heads == {}
