"""Přestavba `intake_milestones` na stav `proposed` (docs/navrhy/2026-10-30-metriky-a-spoustece.md §5): stará databáze
s řádky je nese dál, nová se nepřestavuje, druhé spuštění nic neudělá a index „jeden aktivní na oblast“ platí."""
import sqlite3

import pytest

from database.schema.project_initialization import initialize_project_schema
from database.schema.project_schema import ensure_milestone_proposed

OLD = """
CREATE TABLE intake_milestones(
    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, area_id TEXT NOT NULL, title TEXT NOT NULL,
    criteria TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL CHECK(status IN ('active','done','superseded')),
    created_at TEXT NOT NULL);
CREATE UNIQUE INDEX intake_milestones_one_active
    ON intake_milestones(workspace_id, area_id) WHERE status='active';
"""
ROWS = [("ms_1", "w", "a1", "Spolehlivé hledání", '[{"id":"c1","text":"t","cards":["n1"]}]', "active", "t1"),
        ("ms_0", "w", "a1", "Starší", "[]", "superseded", "t0")]


def table_sql(db):
    return db.execute("SELECT sql FROM sqlite_master WHERE name='intake_milestones'").fetchone()[0]


def insert(db, *row):
    db.execute("INSERT INTO intake_milestones(id,workspace_id,area_id,title,criteria,status,created_at) VALUES(?,?,?,?,?,?,?)", row)


def assert_rules(db):
    insert(db, "ms_p", "w", "a1", "Návrh", "[]", "proposed", "t2")  # nový stav projde
    with pytest.raises(sqlite3.IntegrityError):
        insert(db, "ms_x", "w", "a1", "Druhý aktivní", "[]", "active", "t3")  # index jednoho aktivního platí
    with pytest.raises(sqlite3.IntegrityError):
        insert(db, "ms_y", "w", "a2", "Špatný stav", "[]", "rejected", "t3")
    assert db.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='intake_milestones'"
                      " AND name='intake_milestones_one_active'").fetchone() is not None


def test_old_database_keeps_rows_and_accepts_proposed_twice_without_change():
    db = sqlite3.connect(":memory:")
    db.executescript(OLD)
    for row in ROWS:
        insert(db, *row)
    db.commit()
    initialize_project_schema(db)
    assert "'proposed'" in table_sql(db)
    assert db.execute("SELECT id,workspace_id,area_id,title,criteria,status,created_at FROM intake_milestones ORDER BY id").fetchall() == sorted(ROWS)
    assert db.execute("SELECT name FROM sqlite_master WHERE name='intake_milestones_old'").fetchone() is None
    rebuilt = table_sql(db)
    ensure_milestone_proposed(db)  # druhé spuštění: CHECK už `proposed` zná
    assert table_sql(db) == rebuilt and len(db.execute("SELECT * FROM intake_milestones").fetchall()) == 2
    assert_rules(db)


def test_new_database_is_not_rebuilt_and_has_the_rules():
    db = sqlite3.connect(":memory:")
    initialize_project_schema(db)
    before = table_sql(db)
    ensure_milestone_proposed(db)
    assert table_sql(db) == before and "'proposed'" in before
    insert(db, *ROWS[0])
    assert_rules(db)


def test_failed_rebuild_keeps_the_old_table_and_rows(monkeypatch):
    db = sqlite3.connect(":memory:")
    db.executescript(OLD)
    insert(db, *ROWS[0])
    db.commit()
    monkeypatch.setattr("database.schema.project_schema.MILESTONES_INDEX", "CREATE BROKEN")
    with pytest.raises(sqlite3.OperationalError):
        ensure_milestone_proposed(db)
    assert "'proposed'" not in table_sql(db)
    assert db.execute("SELECT * FROM intake_milestones").fetchall() == [ROWS[0]]
