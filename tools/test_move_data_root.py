import json
import os
import socket
import sqlite3
import subprocess
import tomllib

import pytest

from database.schema.project_schema import REGISTRY_SCHEMA
from tools.move_data_root import LOG_NAME, moved, run, set_toml_value

PID = "a" * 32
EMPTY = "b" * 32


def git(root, *args):
    return subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@example.invalid", "-C", str(root), *args],
                          check=True, capture_output=True, text=True).stdout.strip()


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def fake_root(tmp_path, port=None):
    """Datová složka jako v produkci: git projekt s worktree, prázdný projekt, archiv a cizí lokální cesta."""
    old = (tmp_path / "old").resolve()
    main = old / "projects" / PID / "main"
    main.mkdir(parents=True)
    git(main, "init", "-q", "-b", "main")
    (main / "README.md").write_text("base")
    git(main, "add", ".")
    git(main, "commit", "-q", "-m", "initial")
    worktree = old / "projects" / PID / "worktrees" / "abcd1234"
    git(main, "worktree", "add", "-q", "-b", "work/x", str(worktree))
    empty_main = old / "projects" / EMPTY / "main"
    empty_main.mkdir(parents=True)
    (old / "projects" / EMPTY / "project.json").write_text(json.dumps(
        {"id": EMPTY, "name": "Prázdný", "source": {"kind": "empty", "value": str(empty_main), "branch": ""}}), encoding="utf-8")
    db = sqlite3.connect(old / "registry.sqlite")
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(REGISTRY_SCHEMA)
    outside = str(tmp_path / "elsewhere" / "repo")
    db.execute("INSERT INTO projects VALUES(?,?,?,?,?)", (PID, "Git", str(main), "fixture://x", "main"))
    db.execute("INSERT INTO projects VALUES(?,?,?,?,?)", ("local", "Lokální", outside, "", ""))
    db.execute("INSERT INTO project_sources VALUES(?,?,?)", (EMPTY, "empty", str(empty_main).replace("\\", "/").upper()
                                                            if os.name == "nt" else str(empty_main)))
    db.execute("INSERT INTO workspaces VALUES(?,?,?,?,?,?,?)", ("w" * 32, PID, str(worktree), "work/x", "n", "A", "sha"))
    snapshot = {"project": {"repo": str(main), "note": "viz .data/production"}, "workspaces": [{"directory": str(worktree)}]}
    db.execute("INSERT INTO archived_projects VALUES(?,?,?)", ("gone", json.dumps(snapshot), "2026-01-01"))
    db.commit()
    db.close()
    config = tmp_path / "opora.toml"
    config.write_text(f'[app]\nhost = "127.0.0.1"\nport = {port or free_port()}\ndata = "old"\n'
                      '[profiles.dev]\ndata = "old"\n[profiles.preview]\ndata = ".data/preview"\n', encoding="utf-8")
    local = tmp_path / "opora.local.toml"
    local.write_text('# lokální\n[integrations]\ngraphify_python = "C:/py/python.exe"\n', encoding="utf-8")
    return old, config, local, worktree


def registry(root):
    db = sqlite3.connect(root / "registry.sqlite")
    try:
        return {
            "repo": dict(db.execute("SELECT id, repo FROM projects")),
            "source": db.execute("SELECT source_path FROM project_sources").fetchone()[0],
            "directory": db.execute("SELECT directory FROM workspaces").fetchone()[0],
            "snapshot": json.loads(db.execute("SELECT snapshot FROM archived_projects").fetchone()[0]),
        }
    finally:
        db.close()


def test_move_rewrites_every_stored_path_and_repairs_worktree(tmp_path):
    old, config, local, _ = fake_root(tmp_path)
    new = (tmp_path / "far" / "opora-data").resolve()
    lines = []
    assert run(old, new, config_path=config, local_path=local, out=lines.append) == 0
    assert not old.exists()
    values = registry(new)
    main, worktree = new / "projects" / PID / "main", new / "projects" / PID / "worktrees" / "abcd1234"
    assert values["repo"] == {PID: str(main), "local": str(tmp_path / "elsewhere" / "repo")}
    assert os.path.normcase(values["source"]) == os.path.normcase(str(new / "projects" / EMPTY / "main"))
    assert values["directory"] == str(worktree)
    assert values["snapshot"]["project"] == {"repo": str(main), "note": "viz .data/production"}
    assert values["snapshot"]["workspaces"] == [{"directory": str(worktree)}]
    identity = json.loads((new / "projects" / EMPTY / "project.json").read_text(encoding="utf-8"))
    assert identity["source"]["value"] == str(new / "projects" / EMPTY / "main")
    # Worktree po opravě funguje oběma směry.
    assert git(worktree, "rev-parse", "--abbrev-ref", "HEAD") == "work/x"
    listed = git(main, "worktree", "list", "--porcelain")
    assert worktree.as_posix().lower() in listed.replace("\\", "/").lower()
    settings = tomllib.loads(local.read_text(encoding="utf-8"))
    assert settings["app"]["data"] == new.as_posix()
    assert settings["profiles"]["dev"]["data"] == new.as_posix()
    assert "preview" not in settings.get("profiles", {})
    assert settings["integrations"]["graphify_python"] == "C:/py/python.exe"
    assert local.read_text(encoding="utf-8").startswith("# lokální")
    log = json.loads((new / LOG_NAME).read_text(encoding="utf-8"))
    assert log["oldRoot"] == str(old) and len(log["changes"]) == 5
    assert any("abcd1234" in line for line in lines)


def test_move_back_restores_the_original_paths(tmp_path):
    old, config, local, worktree = fake_root(tmp_path)
    before = registry(old)
    new = (tmp_path / "far").resolve()
    assert run(old, new, config_path=config, local_path=local, out=lambda _: None) == 0
    assert run(new, old, config_path=config, local_path=local, out=lambda _: None) == 0
    after = registry(old)
    assert after["repo"] == before["repo"] and after["directory"] == before["directory"]
    assert git(worktree, "rev-parse", "--abbrev-ref", "HEAD") == "work/x"
    assert tomllib.loads(local.read_text(encoding="utf-8"))["app"]["data"] == old.as_posix()


def test_dry_run_reports_but_touches_nothing(tmp_path):
    old, config, local, _ = fake_root(tmp_path)
    before, local_before = registry(old), local.read_text(encoding="utf-8")
    new = tmp_path / "far"
    lines = []
    assert run(old, new, dry_run=True, config_path=config, local_path=local, out=lines.append) == 0
    assert not new.exists()
    assert registry(old) == before
    assert local.read_text(encoding="utf-8") == local_before
    assert sum("změnilo by se" in line for line in lines) == 5 + 1 + 2


@pytest.mark.parametrize("case", ["port", "nonempty", "inside", "noregistry"])
def test_move_refuses_unsafe_situations(tmp_path, case):
    listener = socket.socket()
    try:
        port = None
        if case == "port":
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = listener.getsockname()[1]
        old, config, local, _ = fake_root(tmp_path, port)
        new = tmp_path / "far"
        if case == "nonempty":
            new.mkdir()
            (new / "x").write_text("x")
        if case == "inside":
            new = old / "nested"
        if case == "noregistry":
            (old / "registry.sqlite").unlink()
            for leftover in old.glob("registry.sqlite-*"):
                leftover.unlink()
        lines = []
        assert run(old, new, config_path=config, local_path=local, out=lines.append) == 1
        assert "odmítnuto" in lines[0]
        assert old.exists()
    finally:
        listener.close()


def test_moved_matches_only_the_old_root_prefix(tmp_path):
    old, new = tmp_path / "data", tmp_path / "new"
    assert moved(str(old / "projects" / "x"), old, new) == str(new / "projects" / "x")
    assert moved(str(old), old, new) == str(new)
    assert moved(str(tmp_path / "data2" / "x"), old, new) is None
    assert moved("viz .data/production", old, new) is None
    assert moved(None, old, new) is None
    if os.name == "nt":
        assert moved(str(old / "x").upper().replace("\\", "/"), old, new).lower() == str(new / "X").lower()


def test_set_toml_value_keeps_other_sections():
    text = '# k\n[integrations]\ngraphify_python = "p"\n'
    result = set_toml_value(text, "app", "data", "D:/opora-data")
    assert tomllib.loads(result) == {"integrations": {"graphify_python": "p"}, "app": {"data": "D:/opora-data"}}
    again = set_toml_value(result, "app", "data", "E:/x")
    assert tomllib.loads(again)["app"]["data"] == "E:/x" and again.count("[app]") == 1
