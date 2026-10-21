"""Migration and restore integration coverage for the context journal."""
import json
import sqlite3

import pytest

from database.repositories.opora_context_events import checkpoint, enroll, transitions
from database.repositories.opora_context_events_sources import SOURCES
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

def test_registered_copy_preserves_counters_with_initialized_target(db):
    from backend.canvas.migrate_to_project_folders import _copy_rows

    begin(db)
    insert(db, "desktop_v3_state")
    db.execute("UPDATE desktop_v3_state SET revision=2,state='changed'")
    db.commit()
    target = sqlite3.connect(":memory:")
    initialize_project_schema(target)
    for table, column in PROJECT_TABLES.items():
        _copy_rows(db, target, table, f"WHERE {column}=?", ("p",))
    for table in TABLES:
        assert target.execute(f"SELECT * FROM {table}").fetchall() == db.execute(f"SELECT * FROM {table}").fetchall()
    assert checkpoint(target, "p") == checkpoint(db, "p")
    target.close()


def test_architecture_real_writer_preserves_graph_and_removed_aba(db):
    from backend.canvas.project_architecture import ProjectArchitecture

    begin(db)
    store = ProjectArchitecture(None)
    original = {"nodes": [{"id": "home"}], "edges": []}
    empty = {"nodes": [], "edges": []}
    assert store.write(db, "p", original, 0, "human", "main") == 1
    assert store.write(db, "p", empty, 1, "human", "main") == 2
    assert store.write(db, "p", original, 2, "human", "main") == 3
    events = transitions(db, "p", 0)
    assert [event["sourceTable"] for event in events] == ["project_architecture"] * 5
    assert [event["operation"] for event in events] == ["INSERT", "DELETE", "INSERT", "DELETE", "INSERT"]
    first, removed, restored = [events[index]["after"] for index in (0, 2, 4)]
    assert json.loads(first["graph"]) == json.loads(restored["graph"]) == original
    assert json.loads(first["removed"]) == json.loads(restored["removed"]) == {"nodes": [], "edges": []}
    assert json.loads(removed["graph"]) == empty
    assert json.loads(removed["removed"]) == {"nodes": ["home"], "edges": []}
    assert [row["revision"] for row in (first, removed, restored)] == [1, 2, 3]
    assert events[1]["before"] == first
    assert events[3]["before"] == removed
    assert all(row["actor"] == "human" and row["updated_at"] for row in (first, removed, restored))


def test_actual_folder_migration_preserves_profile_goal_and_architecture(tmp_path):
    from backend.canvas.migrate_to_project_folders import migrate
    from database.schema.project_schema import REGISTRY_SCHEMA

    source = sqlite3.connect(tmp_path / "canvas.sqlite")
    initialize_project_schema(source)
    source.executescript(REGISTRY_SCHEMA)
    begin(source)
    source.execute("INSERT INTO project_profile VALUES('p','layered','single')")
    source.execute("INSERT INTO project_settings VALUES('p',7,'keep goal','web')")
    from backend.canvas.project_architecture import ProjectArchitecture
    store = ProjectArchitecture(None)
    graph = {"nodes": [{"id": "home"}], "edges": []}
    store.write(source, "p", graph, 0, "human", "main")
    store.write(source, "p", {"nodes": [], "edges": []}, 1, "human", "main")
    source.commit()
    expected = {table: source.execute(f"SELECT * FROM {table}").fetchall()
                for table in ("project_profile", "project_settings", "project_architecture", "project_architecture_revisions", *TABLES)}
    source.close()
    assert migrate(tmp_path)["migrated"]
    target = sqlite3.connect(tmp_path / "projects" / "p" / "project.sqlite")
    for table, rows in expected.items():
        assert target.execute(f"SELECT * FROM {table}").fetchall() == rows
    target.execute("PRAGMA recursive_triggers=ON")
    # The old schema pin remains evidence, never silently rebound to a fresh database.
    with pytest.raises(ValueError, match="schema generation"):
        checkpoint(target, "p")
    target.close()
