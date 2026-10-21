"""Real registry schema and SQL writers exercise lifecycle/source ABA fences."""
import sqlite3

import pytest

from database.repositories.opora_context_bindings import checkpoint, enroll, install
from database.schema.project_schema import REGISTRY_SCHEMA


@pytest.fixture
def db(tmp_path):
    connection = sqlite3.connect(tmp_path / "registry.sqlite")
    connection.executescript(REGISTRY_SCHEMA)
    install(connection)
    connection.execute("INSERT INTO builtin_project_metadata VALUES('draft','Draft')")
    for pid in ("p", "q"):
        connection.execute("INSERT INTO projects VALUES(?,?,?,?,?)", (pid, pid, '/repo', None, 'main'))
        connection.execute("INSERT INTO project_sources VALUES(?,?,?)", (pid, 'local', '/local'))
    connection.commit()
    yield connection
    connection.close()


def start(db, project="p", workspace="draft"):
    db.execute("BEGIN")
    result = enroll(db, project, workspace)
    db.commit()
    return result


@pytest.mark.parametrize("table,column", [("projects", "name"), ("project_sources", "source_path")])
def test_project_source_aba_and_unrelated_project(db, table, column):
    before, other = start(db), start(db, "q")
    key = "id" if table == "projects" else "project_id"
    old = db.execute(f"SELECT {column} FROM {table} WHERE {key}='p'").fetchone()[0]
    db.execute(f"UPDATE {table} SET {column}='changed' WHERE {key}='p'")
    db.execute(f"UPDATE {table} SET {column}=? WHERE {key}='p'", (old,))
    after = checkpoint(db, 'p', 'draft')
    assert after['sources'] == before['sources']
    assert after['generation'] == before['generation'] + 2
    assert checkpoint(db, 'q', 'draft') == other


def test_builtin_and_local_draft_rules(db):
    original = start(db, 'draft')
    db.execute("UPDATE builtin_project_metadata SET name='Other'")
    db.execute("UPDATE builtin_project_metadata SET name='Draft'")
    assert checkpoint(db, 'draft', 'draft')['generation'] == original['generation'] + 2
    for pid, wid in [('missing', 'draft'), ('draft', 'main'), ('p', 'main')]:
        with pytest.raises(ValueError):
            enroll(db, pid, wid)


def test_workspace_aba_move_and_unrelated_workspace(db):
    db.execute("UPDATE project_sources SET source_kind='git'")
    for wid in ('w', 'x'):
        db.execute("INSERT INTO workspaces VALUES(?, 'p','dir','branch','node','actor','sha')", (wid,))
    db.commit()
    first, second = start(db, 'p', 'w'), start(db, 'p', 'x')
    db.execute("UPDATE workspaces SET project_id='q',id='moved' WHERE id='w'")
    with pytest.raises(ValueError):
        checkpoint(db, 'p', 'w')
    db.execute("UPDATE workspaces SET project_id='p',id='w' WHERE id='moved'")
    assert checkpoint(db, 'p', 'w')['generation'] == first['generation'] + 2
    assert checkpoint(db, 'p', 'x') == second


@pytest.mark.parametrize("table,statement", [
    ('archived_projects', "INSERT INTO archived_projects VALUES('p','{}','now')"),
    ('archived_workspaces', "INSERT INTO archived_workspaces VALUES('draft','p',NULL,NULL,NULL,NULL,NULL,'closed','now')"),
])
def test_archive_and_return_never_matches_origin(db, table, statement):
    before = start(db)
    db.execute(statement)
    with pytest.raises(ValueError):
        checkpoint(db, 'p', 'draft')
    db.execute(f"DELETE FROM {table}")
    assert checkpoint(db, 'p', 'draft')['generation'] == before['generation'] + 2


def test_replace_and_rollback(db):
    before = start(db)
    db.execute("BEGIN")
    db.execute("INSERT OR REPLACE INTO project_sources VALUES('p','local','/local')")
    assert checkpoint(db, 'p', 'draft')['generation'] == before['generation'] + 2
    db.rollback()
    assert checkpoint(db, 'p', 'draft') == before


def test_project_delete_reinsert_and_source_identity_moves(db):
    before = start(db)
    project = db.execute("SELECT * FROM projects WHERE id='p'").fetchone()
    db.execute("DELETE FROM projects WHERE id='p'")
    with pytest.raises(ValueError):
        checkpoint(db, 'p', 'draft')
    db.execute("INSERT INTO projects VALUES(?,?,?,?,?)", project)
    assert checkpoint(db, 'p', 'draft')['generation'] == before['generation'] + 2
    db.execute("DELETE FROM project_sources WHERE project_id='q'")
    db.commit()
    other = start(db, 'q', 'main')
    db.execute("UPDATE project_sources SET project_id='q' WHERE project_id='p'")
    db.execute("UPDATE project_sources SET project_id='p' WHERE project_id='q'")
    assert checkpoint(db, 'p', 'draft')['generation'] == before['generation'] + 4
    assert checkpoint(db, 'q', 'main')['generation'] == other['generation'] + 2


def test_writer_disabled_recursive_triggers_freezes_permanently(db):
    start(db)
    path = db.execute("PRAGMA database_list").fetchone()[2]
    with sqlite3.connect(path) as foreign:
        foreign.execute("PRAGMA recursive_triggers=OFF")
        foreign.execute("INSERT OR REPLACE INTO project_sources VALUES('p','local','/other')")
    with pytest.raises(ValueError, match='coverage unavailable'):
        checkpoint(db, 'p', 'draft')


def test_dropped_guard_not_repaired_or_rebound(db):
    start(db)
    sql = db.execute("SELECT sql FROM sqlite_master WHERE name='opora_binding_projects_update'").fetchone()[0]
    db.execute("DROP TRIGGER opora_binding_projects_update")
    db.execute("UPDATE projects SET name='uncovered' WHERE id='p'")
    install(db)
    with pytest.raises(ValueError):
        checkpoint(db, 'p', 'draft')
    db.execute(sql)
    with pytest.raises(ValueError):
        enroll(db, 'p', 'draft')


def test_identity_guards_and_reopen(db):
    before = start(db)
    for sql in ["DELETE FROM opora_context_bindings", "UPDATE opora_context_bindings SET generation=-1",
                "UPDATE opora_context_bindings SET identity='replacement'",
                "INSERT OR REPLACE INTO opora_context_bindings SELECT * FROM opora_context_bindings"]:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(sql)
    db.rollback()
    path = db.execute("PRAGMA database_list").fetchone()[2]
    with sqlite3.connect(path) as reopened:
        install(reopened)
        assert checkpoint(reopened, 'p', 'draft') == before


def test_transaction_and_bounded_sources(db):
    with pytest.raises(RuntimeError):
        enroll(db, 'p', 'draft')
    db.execute("UPDATE projects SET name=? WHERE id='p'", ('x' * 8193,))
    with pytest.raises(ValueError, match='bounds'):
        enroll(db, 'p', 'draft')
