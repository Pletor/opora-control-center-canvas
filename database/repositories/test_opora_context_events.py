"""Raw journal contract: direct SQL, transactional coverage and fail-closed evidence."""
import json
import sqlite3

import pytest

from backend.canvas.opora_context_restore import refuse_context_restore
from backend.canvas.workspace_graph_storage import refuse_authority_restore
from database.repositories.opora_context_events import checkpoint, enroll, install, transitions
from database.repositories.opora_context_events_sources import EVENT_LIMIT, SOURCES
from database.repositories.opora_context_events_triggers import statements
from database.schema.opora_context_event_schema import TABLES
from database.schema.project_initialization import initialize_project_schema
from database.schema.project_schema import PROJECT_TABLES


@pytest.fixture
def db():
    connection = sqlite3.connect(":memory:")
    initialize_project_schema(connection)
    connection.commit()
    yield connection
    connection.close()


def begin(db, project="p"):
    if not db.in_transaction:
        db.execute("BEGIN IMMEDIATE")
    return enroll(db, project)


def insert(db, table, project="p", replace=False):
    values = [1 if key == "revision" else project if key == "project_id" else "x"
              for key in SOURCES[table]]
    verb = "INSERT OR REPLACE" if replace else "INSERT"
    db.execute(f"{verb} INTO {table} VALUES({','.join('?' for _ in values)})", values)


@pytest.mark.parametrize("table", SOURCES)
def test_every_source_raw_operations(db, table):
    insert(db, table)
    assert db.execute("SELECT count(*) FROM opora_context_events").fetchone()[0] == 0
    begin(db)
    db.execute(f"UPDATE {table} SET revision=2" if "revision" in SOURCES[table]
               else f"UPDATE {table} SET architecture='new'")
    db.execute(f"DELETE FROM {table}")
    insert(db, table)
    events = transitions(db, "p", 0)
    assert [event["operation"] for event in events] == ["UPDATE", "DELETE", "INSERT"]
    assert events[0]["before"] == {column: 1 if column == "revision" else "p" if column == "project_id" else "x" for column in SOURCES[table]}
    assert events[1]["after"] is None
    assert events[2]["before"] is None


def test_replace_aba_moves_and_rollback(db):
    first = begin(db)
    begin(db, "q")
    insert(db, "project_profile")
    insert(db, "project_profile", replace=True)
    assert [event["operation"] for event in transitions(db, "p", 0)] == ["INSERT", "DELETE", "INSERT"]
    db.execute("UPDATE project_profile SET project_id='q'")
    assert transitions(db, "p", 3)[0]["after"]["project_id"] == "q"
    assert transitions(db, "q", 0)[0]["before"]["project_id"] == "p"
    db.rollback()
    assert not db.execute("SELECT 1 FROM opora_context_coverage").fetchone()
    assert not db.execute("SELECT 1 FROM opora_context_events").fetchone()
    assert begin(db)["coverageId"] != first["coverageId"]


def test_caller_transaction_and_bounded_history(db):
    with pytest.raises(RuntimeError):
        enroll(db, "p")
    begin(db)
    install(db)
    assert db.in_transaction
    for _ in range(3):
        insert(db, "project_profile", replace=True)
    with pytest.raises(ValueError, match="bounds"):
        transitions(db, "p", 0, limit=2)
    assert len(transitions(db, "p", 4)) == 1
    assert transitions(db, "p", 5) == []
    with pytest.raises(ValueError):
        transitions(db, "p", 6)


def test_foreign_writer_and_recursive_off_freeze(tmp_path):
    path = tmp_path / "journal.sqlite"
    db = sqlite3.connect(path)
    initialize_project_schema(db)
    db.commit()
    begin(db)
    db.commit()
    foreign = sqlite3.connect(path)
    foreign.execute("PRAGMA recursive_triggers=ON")
    insert(foreign, "project_profile")
    foreign.commit()
    assert checkpoint(db, "p")["sequence"] == 1
    foreign.execute("PRAGMA recursive_triggers=OFF")
    insert(foreign, "project_profile", replace=True)
    foreign.commit()
    with pytest.raises(ValueError, match="frozen"):
        checkpoint(db, "p")
    assert foreign.execute("SELECT count(*) FROM project_profile").fetchone()[0] == 1
    foreign.close()
    db.close()


def test_quota_freezes_coverage_allows_legacy_write(db):
    begin(db)
    insert(db, "project_profile")
    db.execute("UPDATE project_profile SET architecture=?", (chr(283) * (EVENT_LIMIT // 2),))
    assert len(db.execute("SELECT architecture FROM project_profile").fetchone()[0]) == EVENT_LIMIT // 2
    with pytest.raises(ValueError, match="frozen"):
        checkpoint(db, "p")
    assert db.execute("SELECT count(*) FROM opora_context_events").fetchone()[0] == 1


@pytest.mark.parametrize("mutation", ["missing-trigger", "replaced-trigger", "schema", "counter", "payload", "gap", "tail"])
def test_corruption_unavailable(db, mutation):
    begin(db)
    insert(db, "project_profile")
    if mutation in ("missing-trigger", "replaced-trigger"):
        db.execute("DROP TRIGGER opora_context_project_profile_insert")
        if mutation == "replaced-trigger":
            db.execute("CREATE TRIGGER opora_context_project_profile_insert AFTER INSERT ON project_profile BEGIN SELECT 1; END")
    elif mutation == "schema":
        db.execute("ALTER TABLE project_profile ADD COLUMN surprise TEXT")
    elif mutation == "counter":
        db.execute("UPDATE opora_context_coverage SET sequence=0")
    else:
        name = "opora_context_events_update" if mutation == "payload" else "opora_context_events_delete"
        db.execute(f"DROP TRIGGER {name}")
        if mutation == "payload":
            db.execute("UPDATE opora_context_events SET after_json=replace(after_json,'x','y')")
        else:
            db.execute("DELETE FROM opora_context_events")
        db.execute(statements()[name])
    with pytest.raises(ValueError):
        checkpoint(db, "p")


def test_immutability_and_project_budget(db):
    begin(db)
    insert(db, "project_profile")
    for sql in ("DELETE FROM opora_context_events", "UPDATE opora_context_events SET bytes=0",
                "DELETE FROM opora_context_coverage", "UPDATE opora_context_coverage SET coverage_id='evil'",
                "INSERT OR REPLACE INTO opora_context_events SELECT * FROM opora_context_events",
                "INSERT OR REPLACE INTO opora_context_coverage SELECT * FROM opora_context_coverage"):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(sql)
    db.execute("UPDATE opora_context_coverage SET bytes=134217728")
    db.execute("UPDATE project_profile SET architecture='y'")
    with pytest.raises(ValueError, match="frozen"):
        checkpoint(db, "p")


@pytest.mark.parametrize("table", TABLES)
def test_restore_refuses_each_table_even_orphan_and_registered(db, table):
    assert PROJECT_TABLES[table] == "project_id"
    begin(db)
    insert(db, "project_profile")
    if table == "opora_context_events":
        db.execute("DROP TRIGGER opora_context_coverage_delete")
        db.execute("DELETE FROM opora_context_coverage")
    else:
        db.execute("DROP TRIGGER opora_context_events_delete")
        db.execute("DELETE FROM opora_context_events")
    with pytest.raises(ValueError, match="context"):
        refuse_context_restore(db)
    with pytest.raises(ValueError, match="context"):
        refuse_authority_restore(db)


def test_missing_source_and_malformed_json(db):
    db.execute("DROP TABLE project_profile")
    with pytest.raises(ValueError):
        begin(db)


def test_history_cap_freezes_and_remains_frozen(db):
    begin(db)
    db.execute("UPDATE opora_context_coverage SET sequence=4096")
    insert(db, "project_profile")
    assert db.execute("SELECT frozen FROM opora_context_coverage").fetchone()[0]
    db.execute("UPDATE project_profile SET architecture='legacy'")
    assert db.execute("SELECT architecture FROM project_profile").fetchone()[0] == "legacy"
    assert not db.execute("SELECT 1 FROM opora_context_events").fetchone()
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE opora_context_coverage SET frozen=NULL")


def test_malformed_payload_is_not_returned(db):
    identity = begin(db)["coverageId"]
    db.execute("INSERT INTO opora_context_events VALUES(?,1,?,'project_profile','INSERT',NULL,'{}',2)", ("p", identity))
    with pytest.raises(ValueError, match="row"):
        checkpoint(db, "p")


def test_reopen_preserves_trigger_generation_and_opt_in(tmp_path):
    path = tmp_path / "db.sqlite"
    db = sqlite3.connect(path)
    initialize_project_schema(db)
    db.commit()
    original = begin(db)
    db.commit()
    db.close()
    db = sqlite3.connect(path)
    initialize_project_schema(db)
    assert checkpoint(db, "p") == original
    assert db.execute("SELECT count(*) FROM opora_context_coverage").fetchone()[0] == 1
    db.close()


def test_source_rollback_preserves_enrolled_checkpoint(db):
    original = begin(db)
    db.commit()
    insert(db, "project_profile")
    assert checkpoint(db, "p")["sequence"] == 1
    db.rollback()
    assert checkpoint(db, "p") == original


def test_invalid_blob_freezes_instead_of_rejecting_legacy(db):
    begin(db)
    db.execute("INSERT INTO project_profile VALUES('p',?, 'legacy')", (b"raw",))
    assert db.execute("SELECT typeof(architecture) FROM project_profile").fetchone()[0] == "blob"
    with pytest.raises(ValueError, match="frozen"):
        checkpoint(db, "p")


def test_history_overflow_fails_without_returning_prefix(db):
    begin(db)
    insert(db, "project_profile")
    for index in range(256):
        db.execute("UPDATE project_profile SET architecture=?", (str(index),))
    with pytest.raises(ValueError, match="bounds"):
        transitions(db, "p", 0)
    assert len(transitions(db, "p", 1)) == 256
