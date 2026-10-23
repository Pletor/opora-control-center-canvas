"""Tabulky design náhledu přibydou do starého project.sqlite při otevření a nic stávajícího nezmění."""
import sqlite3

from database.schema.opora_design_preview_schema import TABLES
from database.schema.project_initialization import initialize_project_schema
from database.schema.project_schema import PROJECT_TABLES

OLD_DRAWING_FILES = """CREATE TABLE drawing_files(
    project_id TEXT NOT NULL, file_id TEXT NOT NULL, mime_type TEXT NOT NULL,
    data BLOB NOT NULL, created_at TEXT NOT NULL,
    PRIMARY KEY(project_id, file_id))"""


def tables(db):
    return {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_old_project_database_gains_the_preview_tables_and_keeps_its_rows():
    db = sqlite3.connect(":memory:")
    db.execute(OLD_DRAWING_FILES)
    db.execute("INSERT INTO drawing_files VALUES('p','img','image/png',x'89504e47','t')")
    db.commit()
    assert not set(TABLES) & tables(db)
    initialize_project_schema(db)
    assert set(TABLES) <= tables(db)
    initialize_project_schema(db)  # idempotent
    assert db.execute("SELECT file_id FROM drawing_files").fetchall() == [("img",)]
    db.execute("INSERT INTO opora_design_modes VALUES('p','w','card','explore',1,'human','t')")
    columns = [row[1] for row in db.execute("PRAGMA table_info(opora_design_previews)")]
    assert columns == ["project_id", "workspace_id", "execution_id", "head_sha", "node_id", "pr_number", "record",
                       "by", "created_at", "updated_at"]


def test_preview_tables_belong_to_one_project():
    assert set(TABLES) <= PROJECT_TABLES.keys()
