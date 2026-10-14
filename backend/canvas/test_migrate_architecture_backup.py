"""Záloha a návrat migrace architektury: bajtová obnova, odmítnutí po pozdější změně, force."""

import pytest

import backend.canvas.migrate_architecture as module
from backend.canvas.migrate_architecture import migrate
from backend.canvas.migrate_architecture_backup import database_digest, down, read_manifest
from backend.canvas.test_canvas_service import managed_fixture
from backend.canvas.test_graph_card import node
from backend.canvas.test_migrate_architecture import old_workspace, put, site_graph


@pytest.fixture
def git_project(tmp_path):
    s, p = managed_fixture(tmp_path)
    yield s, p["id"], *sorted([old_workspace(s, p["id"], "Agent A"), old_workspace(s, p["id"], "Agent B")])
    s.close()


def db_digest(s, pid):
    with s.lock_for(pid):
        return database_digest(s.db_for(pid))


def test_backup_manifest_and_down_restore_bytes(git_project):
    s, pid, a, b = git_project
    put(s, pid, a, site_graph())  # b nemá graf v datech: v manifestu jako chybějící soubor
    before_files = {wid: s.graph_file(pid, wid).read_bytes() if s.graph_file(pid, wid).exists() else None for wid in (a, b)}
    before_db, before_view = db_digest(s, pid), s.view(pid, a)

    report = migrate(s, pid, dry_run=False)
    manifest = read_manifest(s, pid, report["backup"])
    assert [item["existed"] for item in manifest["files"]] == [before_files[w] is not None for w in sorted((a, b))]
    assert manifest["missing"] == [f"canvas/workspaces/{b}/graph.json"] and manifest["after"] is not None
    assert s.graph_file(pid, a).read_bytes() != before_files[a]

    restored = down(s, pid, report["backup"])
    assert restored["phase"] == "restored"
    assert s.graph_file(pid, a).read_bytes() == before_files[a] and not s.graph_file(pid, b).exists()
    assert db_digest(s, pid) == before_db
    assert s.db_for(pid).execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert s.architecture.read(pid)["revision"] == 0
    assert s.view(pid, a)["digest"] == before_view["digest"]
    # Stav migrace se vrátil také: náhled jde spustit znovu.
    assert migrate(s, pid)["phase"] == "dry-run"
    with pytest.raises(ValueError, match="už byla vrácena"):
        down(s, pid, report["backup"])


def test_down_refuses_after_later_change_unless_forced(git_project):
    s, pid, a, _b = git_project
    put(s, pid, a, site_graph())
    original = s.graph_file(pid, a).read_bytes()
    report = migrate(s, pid, dry_run=False)
    view = s.view(pid, a)
    s.save_graph(pid, a, {"nodes": [*view["graph"]["nodes"], node("later")], "edges": view["graph"]["edges"]},
                 view["digest"], actor="human")
    with pytest.raises(ValueError, match="změnilo"):
        down(s, pid, report["backup"])
    down(s, pid, report["backup"], force=True)
    assert s.graph_file(pid, a).read_bytes() == original


def test_down_refuses_unfinished_migration_without_force(git_project, monkeypatch):
    s, pid, a, _b = git_project
    put(s, pid, a, site_graph())
    original = s.graph_file(pid, a).read_bytes()

    def crash(*_args):
        raise RuntimeError("pád")

    monkeypatch.setitem(module.STEPS, "docs", crash)
    with pytest.raises(RuntimeError):
        migrate(s, pid, dry_run=False)
    backup = migrate(s, pid)["backup"]
    with pytest.raises(ValueError, match="nedoběhla"):
        down(s, pid, backup)
    down(s, pid, backup, force=True)
    assert s.architecture.read(pid)["revision"] == 0 and s.graph_file(pid, a).read_bytes() == original


def test_invalid_backup_id_is_rejected(git_project):
    s, pid, _a, _b = git_project
    with pytest.raises(ValueError, match="Neplatné ID zálohy"):
        down(s, pid, "../../etc")
