import argparse
import sqlite3

import pytest

from tools.perf import perf_common
from tools.perf.data_copy import copy_data
from tools.perf.perf_common import copy_dir


def _db(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    with db:
        db.execute("CREATE TABLE t(v TEXT)")
        db.execute("INSERT INTO t VALUES(?)", (value,))
    db.close()


def test_copy_backs_up_sqlite_copies_files_and_skips_journals(tmp_path):
    source, target = tmp_path / "src", tmp_path / "dst"
    _db(source / "projects" / "p" / "project.sqlite", "ample")
    (source / "projects" / "p" / "project.sqlite-wal").write_bytes(b"x")
    (source / "notes.json").write_text("{}", encoding="utf-8")
    before = (source / "projects" / "p" / "project.sqlite").read_bytes()

    assert copy_data(source, target) == 2

    db = sqlite3.connect(target / "projects" / "p" / "project.sqlite")
    assert db.execute("SELECT v FROM t").fetchall() == [("ample",)]
    db.close()
    assert (target / "notes.json").read_text(encoding="utf-8") == "{}"
    assert not (target / "projects" / "p" / "project.sqlite-wal").exists()
    assert (source / "projects" / "p" / "project.sqlite").read_bytes() == before


@pytest.mark.parametrize("overlap", ["same", "child", "parent"])
def test_copy_refuses_target_overlapping_source(tmp_path, overlap):
    source = tmp_path / "src"
    source.mkdir()
    target = {"same": source, "child": source / "copy", "parent": tmp_path}[overlap]
    with pytest.raises(ValueError):
        copy_data(source, target)


def test_copy_refuses_non_empty_target(tmp_path):
    source, target = tmp_path / "src", tmp_path / "dst"
    source.mkdir()
    target.mkdir()
    (target / "old").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        copy_data(source, target)


def test_benchmarks_refuse_live_data(tmp_path, monkeypatch):
    live, copy = tmp_path / "production", tmp_path / "perf-copy"
    (live / "projects").mkdir(parents=True)
    copy.mkdir()
    monkeypatch.setattr(perf_common, "LIVE_DATA", live)

    assert copy_dir(str(copy)) == str(copy.resolve())
    for path in (live, live / "projects"):
        with pytest.raises(argparse.ArgumentTypeError, match="kopii"):
            copy_dir(str(path))


def test_benchmarks_refuse_configured_data_root_outside_repo(tmp_path, monkeypatch):
    # Datová složka přesunutá mimo repozitář (opora.local.toml) je pořád živá data.
    moved, copy = tmp_path / "opora-data", tmp_path / "perf-copy"
    (moved / "projects").mkdir(parents=True)
    copy.mkdir()
    monkeypatch.setattr(perf_common, "configured_data", lambda: moved.resolve())

    assert copy_dir(str(copy)) == str(copy.resolve())
    for path in (moved, moved / "projects"):
        with pytest.raises(argparse.ArgumentTypeError, match="kopii"):
            copy_dir(str(path))


def test_configured_data_reads_opora_config():
    assert perf_common.configured_data().is_absolute()


def test_live_data_points_to_production():
    assert perf_common.LIVE_DATA.parts[-2:] == (".data", "production")


def test_backup_includes_committed_rows_that_live_only_in_the_wal(tmp_path):
    """Karta P3: běžící server drží potvrzená data v -wal; prostá kopie souboru je minula."""
    from tools.perf.data_copy import backup_sqlite

    source = tmp_path / "registry.sqlite"
    live = sqlite3.connect(source)
    live.execute("PRAGMA journal_mode=WAL")
    live.execute("PRAGMA wal_autocheckpoint=0")
    with live:
        live.execute("CREATE TABLE projects(id TEXT)")
        live.execute("INSERT INTO projects VALUES('ample')")
    assert (tmp_path / "registry.sqlite-wal").stat().st_size > 0
    backup_sqlite(source, tmp_path / "backup.sqlite")
    copy = sqlite3.connect(tmp_path / "backup.sqlite")
    assert copy.execute("SELECT id FROM projects").fetchall() == [("ample",)]
    copy.close()
    live.close()
