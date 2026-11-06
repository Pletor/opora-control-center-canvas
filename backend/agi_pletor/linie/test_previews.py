"""Náhledy bez npm a bez serveru (build/spawn jsou podvržené): slug, port, registr, kopie dat, stop, remove."""
import socket
import sqlite3

import pytest

from backend.agi_pletor.linie import previews
from backend.agi_pletor.linie.test_branches import make_repo, run


class Process:
    pid = 4242

    def __init__(self):
        self.code = None

    def poll(self):
        return self.code

    def terminate(self):
        self.code = -15


def data_root(path):
    path.mkdir()
    with sqlite3.connect(path / "registry.sqlite") as db:
        db.execute("create table projects (id text)")
        db.execute("insert into projects values ('p1')")
    db.close()
    for sub in ("brain", "maps", "worktrees"):
        (path / "projects" / "p1" / sub).mkdir(parents=True)
        (path / "projects" / "p1" / sub / "f.txt").write_text(sub, encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def no_junction(monkeypatch):
    monkeypatch.setattr(previews, "_link_node_modules", lambda tree: None)
    previews.RUNNING.clear()


def test_slug():
    assert previews.slug("feat/Velin-Linie_2") == "feat-velin-linie-2"
    assert previews.slug("///") == ""


def test_free_port_skips_protected_taken_and_busy(monkeypatch):
    monkeypatch.setattr(previews, "_listening", lambda port: port == 8792)
    assert previews.free_port({8790}) == 8791
    assert previews.free_port({8790, 8791}) == 8793
    monkeypatch.setattr(previews, "FIRST_PORT", 8740)
    assert previews.free_port() == 8741


def test_listening():
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        assert previews._listening(busy.getsockname()[1]) is True


def test_start_stop_remove(tmp_path):
    repo, folder = make_repo(tmp_path / "r"), tmp_path / "pletor"
    data = data_root(tmp_path / "data")
    built, process = [], Process()
    record = previews.start(folder, repo, "feat/a", "p1", data, "2026-11-06T10:00:00Z",
                            build=lambda tree, log: built.append(tree) or True,
                            spawn=lambda tree, port, data, log: process, run=lambda work: None)
    assert record["state"] == "building" and record["slug"] == "feat-a" and record["port"] >= 8790
    assert record["sha"] == run(repo, "rev-parse", "feat/a")
    assert record["url"] == f"http://127.0.0.1:{record['port']}/?screen=pletor"
    copy = folder / "linie" / "previews" / "feat-a" / "data"
    with sqlite3.connect(copy / "registry.sqlite") as db:
        assert db.execute("select id from projects").fetchall() == [("p1",)]
    db.close()
    assert (copy / "projects" / "p1" / "brain" / "f.txt").exists()
    assert not (copy / "projects" / "p1" / "maps").exists()
    assert not (copy / "projects" / "p1" / "worktrees").exists()
    assert (folder / "linie" / "previews" / "feat-a" / "tree" / "d.txt").exists()
    assert run(repo, "rev-parse", "--abbrev-ref", "HEAD") == "main"  # hlavní strom beze změny

    again = previews.start(folder, repo, "feat/a", "p1", data, "t2",
                           build=lambda tree, log: True, spawn=lambda *a: process, run=lambda work: work())
    assert again["port"] == record["port"]  # existující worktree se použije znovu
    assert [p["state"] for p in previews.status(folder)] == ["running"]
    assert previews.status(folder)[0]["pid"] == 4242
    assert previews.stop(folder, "feat-a")["state"] == "stopped" and process.code == -15
    assert previews.status(folder)[0]["state"] == "stopped"
    assert previews.log(folder, "feat-a") == {"build": "", "server": ""}

    assert previews.remove(folder, repo, "feat-a") == {"slug": "feat-a", "removed": True}
    assert previews.status(folder) == [] and not (folder / "linie" / "previews" / "feat-a").exists()
    assert "feat-a" not in run(repo, "worktree", "list")


def test_failed_build_and_dead_process(tmp_path):
    repo, folder = make_repo(tmp_path / "r"), tmp_path / "pletor"
    data = data_root(tmp_path / "data")
    previews.start(folder, repo, "topic/1-t", "p1", data, "t", build=lambda tree, log: False,
                   spawn=lambda *a: pytest.fail("bez buildu se server nespouští"), run=lambda work: work())
    assert previews.status(folder)[0]["state"] == "failed"
    process = Process()
    previews.start(folder, repo, "feat/a", "p1", data, "t", build=lambda tree, log: True,
                   spawn=lambda *a: process, run=lambda work: work())
    process.code = 1  # proces sám skončil
    assert {p["branch"]: p["state"] for p in previews.status(folder)} == {"topic/1-t": "failed", "feat/a": "stopped"}


def test_start_refuses_unknown_branch(tmp_path):
    repo = make_repo(tmp_path / "r")
    with pytest.raises(ValueError, match="neexistuje"):
        previews.start(tmp_path / "p", repo, "feat/nic", "p1", tmp_path, "t", run=lambda work: None)
    with pytest.raises(KeyError):
        previews.stop(tmp_path / "p", "nic")
