"""Expand-only lifecycle migration preserves old data and never invents historical acceptance."""
import sqlite3

from database.schema.milestone_lifecycle import ensure_milestone_lifecycle
from database.schema.project_initialization import initialize_project_schema
from database.schema.test_milestone_proposed import OLD, ROWS

COLUMNS = "id,workspace_id,area_id,title,criteria,status,created_at"


def test_old_schema_rows_survive_two_full_initializations_with_unknown_provenance():
    db = sqlite3.connect(":memory:")
    db.executescript(OLD)
    db.executemany(f"INSERT INTO intake_milestones({COLUMNS}) VALUES(?,?,?,?,?,?,?)", ROWS)
    db.commit()
    initialize_project_schema(db)
    initialize_project_schema(db)
    assert db.execute(f"SELECT {COLUMNS} FROM intake_milestones ORDER BY id").fetchall() == sorted(ROWS)
    assert db.execute("SELECT replaced_by FROM intake_milestones").fetchall() == [(None,), (None,)]
    # Old binaries' explicit seven-column writes continue working after expansion.
    db.execute(f"INSERT INTO intake_milestones({COLUMNS}) VALUES(?,?,?,?,?,?,?)",
               ("old_writer", "w", "a1", "Legacy writer", "[]", "proposed", "t3"))
    assert db.execute("SELECT replaced_by FROM intake_milestones WHERE id='old_writer'").fetchone() == (None,)


def test_column_only_migration_is_idempotent_without_rewriting_history():
    db = sqlite3.connect(":memory:")
    db.executescript(OLD)
    db.executemany(f"INSERT INTO intake_milestones({COLUMNS}) VALUES(?,?,?,?,?,?,?)", ROWS)
    before = db.execute(f"SELECT {COLUMNS} FROM intake_milestones ORDER BY id").fetchall()
    ensure_milestone_lifecycle(db)
    ensure_milestone_lifecycle(db)
    assert db.execute(f"SELECT {COLUMNS} FROM intake_milestones ORDER BY id").fetchall() == before
