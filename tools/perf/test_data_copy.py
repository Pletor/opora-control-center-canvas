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


def test_live_data_points_to_production():
    assert perf_common.LIVE_DATA.parts[-2:] == (".data", "production")
