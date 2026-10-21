"""Concurrent registry snapshots and conservative migration preservation."""
import sqlite3

import pytest

from backend.canvas.migrate_to_project_folders import migrate
from database.repositories.opora_context_bindings import checkpoint, enroll, install
from database.schema.project_schema import REGISTRY_SCHEMA


def registry(path):
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(REGISTRY_SCHEMA)
    install(db)
    db.execute("INSERT INTO builtin_project_metadata VALUES('draft','Draft')")
    db.commit()
    db.execute("BEGIN")
    before = enroll(db, 'draft', 'draft')
    db.commit()
    return db, before


def test_foreign_commit_between_fence_and_source_read_keeps_one_snapshot(tmp_path):
    path = tmp_path / 'registry.sqlite'
    db, before = registry(path)
    foreign = sqlite3.connect(path)
    foreign.execute("PRAGMA recursive_triggers=ON")
    changed = False

    def trace(sql):
        nonlocal changed
        if not changed and sql.startswith('SELECT * FROM projects'):
            changed = True
            foreign.execute("UPDATE builtin_project_metadata SET name='Changed'")
            foreign.commit()

    db.set_trace_callback(trace)
    try:
        assert checkpoint(db, 'draft', 'draft') == before
        assert changed
        assert not db.in_transaction
        db.set_trace_callback(None)
        after = checkpoint(db, 'draft', 'draft')
        assert after['generation'] == before['generation'] + 1
        assert after['sources']['builtin_project_metadata'] == [['draft', 'Changed']]
    finally:
        foreign.close()
        db.close()


def test_checkpoint_preserves_caller_transaction_and_rollback(tmp_path):
    db, before = registry(tmp_path / 'registry.sqlite')
    try:
        db.execute("BEGIN")
        db.execute("UPDATE builtin_project_metadata SET name='Changed'")
        assert checkpoint(db, 'draft', 'draft')['generation'] == before['generation'] + 1
        assert db.in_transaction
        db.rollback()
        assert checkpoint(db, 'draft', 'draft') == before
    finally:
        db.close()


def test_generation_overflow_freezes_legacy_writer_without_reenrollment(tmp_path):
    db, _ = registry(tmp_path / 'registry.sqlite')
    try:
        db.execute("INSERT INTO projects VALUES('q','Local',NULL,NULL,NULL)")
        db.execute("INSERT INTO project_sources VALUES('q','local','/local')")
        # Seed a valid independent binding at the largest allowed generation.
        db.execute("INSERT INTO opora_context_bindings SELECT 'q','draft',identity,2147483647,schema_digest,trigger_digest,schema_version,frozen FROM opora_context_bindings")
        assert checkpoint(db, 'q', 'draft')['generation'] == 2147483647
        db.execute("UPDATE projects SET name='Changed' WHERE id='q'")
        assert db.execute("SELECT frozen FROM opora_context_bindings WHERE project_id='q'").fetchone()[0] == 'generation exhausted'
        with pytest.raises(ValueError, match='coverage unavailable'):
            enroll(db, 'q', 'draft')
        assert db.execute("SELECT name FROM projects WHERE id='q'").fetchone()[0] == 'Changed'
    finally:
        db.close()


def test_legacy_migration_preserves_binding_without_silently_repairing(tmp_path):
    db, _ = registry(tmp_path / 'canvas.sqlite')
    expected = db.execute("SELECT * FROM opora_context_bindings").fetchall()
    db.close()
    result = migrate(tmp_path)
    assert result['migrated']
    assert result['registry']['opora_context_bindings'] == 1
    with sqlite3.connect(tmp_path / 'registry.sqlite') as copied:
        assert copied.execute("SELECT * FROM opora_context_bindings").fetchall() == expected
        install(copied)
        with pytest.raises(ValueError, match='coverage unavailable'):
            checkpoint(copied, 'draft', 'draft')
