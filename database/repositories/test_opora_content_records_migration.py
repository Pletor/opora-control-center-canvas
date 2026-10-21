"""Content ledgers survive registered migration and block destructive old restores."""
import sqlite3

import pytest

from backend.canvas.migrate_to_project_folders import _copy_rows
from backend.canvas.opora_context_restore import refuse_context_restore
from database.repositories.opora_content_records import ContentRecords
from database.repositories.test_opora_content_records import manifest, proposal
from database.schema.opora_content_schema import TABLES
from database.schema.project_initialization import initialize_project_schema
from database.schema.project_schema import PROJECT_TABLES


def test_registered_copy_and_reopen_preserve_full_records(tmp_path):
    source = sqlite3.connect(tmp_path / "source.sqlite")
    target_path = tmp_path / "target.sqlite"
    target = sqlite3.connect(target_path)
    for db in (source, target):
        initialize_project_schema(db)
        db.commit()
    source.execute("BEGIN IMMEDIATE")
    repo = ContentRecords(source, "p", "w")
    records = [repo.insert(proposal()), repo.insert(manifest(), manifest=True)]
    source.commit()
    for table in TABLES:
        assert PROJECT_TABLES[table] == "project_id"
        _copy_rows(source, target, table, "WHERE project_id=?", ("p",))
    target.commit()
    source.close()
    target.close()
    target = sqlite3.connect(target_path)
    initialize_project_schema(target)
    repo = ContentRecords(target, "p", "w")
    assert repo.read(records[0]["id"]) == records[0]
    assert repo.read(records[1]["id"], manifest=True) == records[1]
    target.close()


@pytest.mark.parametrize("table", TABLES)
def test_orphaned_content_evidence_refuses_historical_restore(table):
    db = sqlite3.connect(":memory:")
    initialize_project_schema(db)
    refuse_context_restore(db)
    db.execute(f"INSERT INTO {table} VALUES('p','w','orphan','{{}}')")
    with pytest.raises(ValueError, match="restore"):
        refuse_context_restore(db)
    db.close()
