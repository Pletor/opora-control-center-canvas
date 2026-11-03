"""Migrace B8: mrtvé tabulky zmizí z kopie staré `project.sqlite`, nic jiného se nezmění."""
import shutil
import sqlite3

import pytest

from database.schema.dead_tables import DEAD_TABLES, drop_dead_tables, drop_retired_tables
from database.schema.project_initialization import initialize_project_schema
from database.schema.project_schema import PROJECT_SCHEMA

# DDL přesně tak, jak leží ve starých project.sqlite (přečteno read-only 23. 10.).
LEGACY_DDL = """
CREATE TABLE node_sessions(
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
    node_id TEXT NOT NULL, source TEXT NOT NULL, session_id TEXT NOT NULL,
    run_id TEXT, role TEXT NOT NULL, title TEXT NOT NULL, parent_session_id TEXT,
    bound_at TEXT NOT NULL, baseline_at TEXT NOT NULL, baseline_cursor INTEGER NOT NULL,
    closed_at TEXT, closed_snapshot TEXT);
CREATE UNIQUE INDEX node_sessions_active
    ON node_sessions(project_id, workspace_id, source, session_id) WHERE closed_at IS NULL;
CREATE INDEX node_sessions_scope ON node_sessions(project_id, workspace_id, node_id);
CREATE TABLE agent_bindings(
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
    layer TEXT NOT NULL, node_id TEXT NOT NULL, source_id TEXT NOT NULL,
    run_id TEXT NOT NULL, session_id TEXT, created_at TEXT NOT NULL);
CREATE TABLE agent_binding_scopes(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL,
    revision INTEGER NOT NULL, PRIMARY KEY(project_id, workspace_id, node_id));
CREATE TABLE agent_activity_entries(
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
    node_id TEXT NOT NULL, source_id TEXT NOT NULL, run_id TEXT NOT NULL,
    source_event_id TEXT NOT NULL, source_timestamp TEXT, ingest_timestamp TEXT NOT NULL,
    kind TEXT NOT NULL, summary TEXT NOT NULL,
    author_type TEXT NOT NULL, source_trust TEXT NOT NULL,
    UNIQUE(project_id, workspace_id, node_id, source_id, run_id, source_event_id));
"""


def objects(db):
    return {row[0] for row in db.execute("SELECT name FROM sqlite_master")}


def dead_objects(db):
    return {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE tbl_name IN (?,?,?,?)", DEAD_TABLES)}


@pytest.fixture
def legacy(tmp_path):
    """Fixture DB ve tvaru staré project.sqlite a její kopie, na které migrace běží."""
    fixture = tmp_path / "fixture.sqlite"
    db = sqlite3.connect(fixture)
    db.executescript(PROJECT_SCHEMA + LEGACY_DDL)
    db.execute("INSERT INTO drafts VALUES('draft','{\"nodes\":[]}')")
    db.commit()
    db.close()
    copy = tmp_path / "project.sqlite"
    shutil.copyfile(fixture, copy)
    return fixture, copy


def test_initialize_drops_dead_tables_on_copy_and_keeps_everything_else(legacy):
    fixture, copy = legacy
    db = sqlite3.connect(copy)
    before = objects(db) - dead_objects(db)
    assert dead_objects(db)
    initialize_project_schema(db)
    db.commit()
    assert not dead_objects(db)
    assert before <= objects(db)
    assert db.execute("SELECT graph FROM drafts WHERE id='draft'").fetchone()[0] == '{"nodes":[]}'
    assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    db.close()
    original = sqlite3.connect(fixture)
    assert set(DEAD_TABLES) <= objects(original)  # kopie, ne originál
    original.close()


def test_drop_is_idempotent_and_does_not_touch_schema_again(legacy):
    _, copy = legacy
    db = sqlite3.connect(copy)
    assert drop_dead_tables(db) == list(DEAD_TABLES)
    initialize_project_schema(db)
    db.commit()
    version = db.execute("PRAGMA schema_version").fetchone()[0]
    assert drop_dead_tables(db) == []
    initialize_project_schema(db)  # druhé otevření projektu: žádné DDL, pokrytí SQL kontextu drží
    db.commit()
    assert db.execute("PRAGMA schema_version").fetchone()[0] == version
    db.close()


def test_table_with_rows_is_kept(legacy):
    _, copy = legacy
    db = sqlite3.connect(copy)
    db.execute("INSERT INTO agent_binding_scopes VALUES('p','w','n',1)")
    assert drop_dead_tables(db) == ["node_sessions", "agent_bindings", "agent_activity_entries"]
    assert db.execute("SELECT count(*) FROM agent_binding_scopes").fetchone()[0] == 1
    db.close()


def test_project_enrolled_in_sql_context_is_left_alone(legacy):
    _, copy = legacy
    db = sqlite3.connect(copy)
    version = db.execute("PRAGMA schema_version").fetchone()[0]
    db.execute("INSERT INTO opora_context_coverage(project_id,coverage_id,schema_digest,trigger_digest,schema_version)"
               " VALUES('draft',?,?,?,?)", ("0" * 32, "s", "t", version))
    assert drop_dead_tables(db) == []
    assert set(DEAD_TABLES) <= objects(db)
    assert db.execute("PRAGMA schema_version").fetchone()[0] == version
    db.close()


def test_fresh_project_has_no_dead_tables(tmp_path):
    db = sqlite3.connect(tmp_path / "project.sqlite")
    initialize_project_schema(db)
    assert drop_dead_tables(db) == []
    assert not dead_objects(db)
    db.close()


# Tabulka staré fronty úkolů mozku tak, jak ležela v project.sqlite do PR 5c (i s daty).
HEART_TASKS_DDL = """
CREATE TABLE heart_tasks(
    seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT, title TEXT NOT NULL, body TEXT NOT NULL,
    status TEXT NOT NULL, session_id TEXT, attempts INTEGER NOT NULL DEFAULT 0, created_by TEXT NOT NULL, report TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, task_order INTEGER NOT NULL DEFAULT 0);
CREATE INDEX heart_tasks_queue ON heart_tasks(project_id, workspace_id, status, seq);
INSERT INTO heart_tasks(id,project_id,workspace_id,title,body,status,created_by,created_at,updated_at)
    VALUES('ht_1','p','draft','Starý úkol','{}','ready','heart','t','t');
"""


def test_retired_heart_tasks_table_is_dropped_with_its_rows_and_index_once(tmp_path):
    db = sqlite3.connect(tmp_path / "project.sqlite")
    db.executescript(PROJECT_SCHEMA + HEART_TASKS_DDL)
    initialize_project_schema(db)
    db.commit()
    assert not {"heart_tasks", "heart_tasks_queue"} & objects(db)
    version = db.execute("PRAGMA schema_version").fetchone()[0]
    assert drop_retired_tables(db) == []
    initialize_project_schema(db)  # druhé otevření: žádné DDL
    assert db.execute("PRAGMA schema_version").fetchone()[0] == version
    db.close()
