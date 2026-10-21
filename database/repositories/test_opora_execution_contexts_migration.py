"""Private origin preservation and historical restore refusal."""
import sqlite3

import pytest

from backend.canvas.migrate_to_project_folders import _copy_rows
from backend.canvas.opora_context_restore import refuse_context_restore
from database.repositories import opora_execution_contexts as contexts
from database.schema.opora_execution_context_schema import TABLES
from database.schema.project_initialization import initialize_project_schema
from database.schema.project_schema import PROJECT_TABLES


def test_registered_migration_preserves_secret_origin_and_latest_proof():
    source, target = sqlite3.connect(":memory:"), sqlite3.connect(":memory:")
    for db in (source, target):
        initialize_project_schema(db)
        db.commit()
    source.execute("BEGIN IMMEDIATE")
    secret = contexts.key(source, "p", create=True)
    contexts.insert(source, "p", "w", "e", {"private": "origin"})
    contexts.proof(source, "p", "w", "e", {"checked": "head"})
    source.commit()
    for table in TABLES:
        assert PROJECT_TABLES[table] == "project_id"
        _copy_rows(source, target, table, "WHERE project_id=?", ("p",))
        assert source.execute(f"SELECT * FROM {table}").fetchall() == target.execute(f"SELECT * FROM {table}").fetchall()
    assert contexts.key(target, "p") == secret
    assert contexts.read(target, "p", "w", "e") == {"private": "origin"}
    assert contexts.read_proof(target, "p", "w", "e") == {"checked": "head"}
    source.close()
    target.close()


@pytest.mark.parametrize("table", TABLES)
def test_restore_refuses_each_populated_table_even_orphaned(table):
    db = sqlite3.connect(":memory:")
    initialize_project_schema(db)
    refuse_context_restore(db)
    if table.endswith("keys"):
        db.execute(f"INSERT INTO {table} VALUES('p','orphan')")
    else:
        db.execute(f"INSERT INTO {table} VALUES('e','p','w','{{}}','orphan',NULL)")
    with pytest.raises(ValueError, match="restore"):
        refuse_context_restore(db)
    db.close()


def test_restore_guard_allows_legacy_database_without_new_tables():
    db = sqlite3.connect(":memory:")
    refuse_context_restore(db)
    db.close()
