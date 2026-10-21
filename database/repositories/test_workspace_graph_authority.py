"""Authority remains transactional and never silently revives legacy file data."""
import json
import sqlite3

import pytest

from backend.canvas.graph import digest
from database.repositories.workspace_graph_authority import WorkspaceGraphAuthority
from database.schema.workspace_graph_authority_schema import SCHEMA

EMPTY = {"nodes": [], "edges": []}
GRAPH = {"nodes": [{"id": "card", "parentId": "shared-architecture", "name": "Úkol"}], "edges": []}


@pytest.fixture
def database(tmp_path):
    db = sqlite3.connect(tmp_path / "project.sqlite")
    db.executescript(SCHEMA)
    yield db
    db.close()


def test_legacy_scope_is_unenrolled_and_cannot_be_written(database):
    store = WorkspaceGraphAuthority(database, "project", "workspace")
    assert store.read() is None
    assert not store.enrolled()
    database.execute("BEGIN IMMEDIATE")
    with pytest.raises(ValueError, match="not enrolled"):
        store.write(EMPTY)
    assert store.read() is None


def test_enrollment_and_writes_require_caller_transaction(database):
    store = WorkspaceGraphAuthority(database, "project", "workspace")
    for operation in (store.enroll, store.write):
        with pytest.raises(RuntimeError, match="existing transaction"):
            operation(EMPTY)
    assert not database.in_transaction


def test_rollback_includes_enrollment_graph_and_companion_writes(database):
    database.execute("CREATE TABLE accepted_head(value)")
    store = WorkspaceGraphAuthority(database, "project", "workspace")
    database.execute("BEGIN IMMEDIATE")
    store.enroll(EMPTY)
    store.write(GRAPH, 1)
    database.execute("INSERT INTO accepted_head VALUES('next')")
    database.rollback()
    assert store.read() is None
    assert database.execute("SELECT * FROM accepted_head").fetchall() == []


def test_restart_and_schema_reapply_preserve_authority_and_original_file(tmp_path):
    legacy = tmp_path / "graph.json"
    legacy.write_text(json.dumps(EMPTY), encoding="utf-8")
    before = legacy.read_bytes()
    path = tmp_path / "project.sqlite"
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)
        db.execute("BEGIN IMMEDIATE")
        store = WorkspaceGraphAuthority(db, "project", "workspace")
        assert store.enroll(EMPTY)["revision"] == 1
        result = store.write(GRAPH, 1)
        assert db.in_transaction
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)
        assert WorkspaceGraphAuthority(db, "project", "workspace").read() == result
        assert result == {"graph": GRAPH, "revision": 2, "digest": digest(GRAPH)}
    assert legacy.read_bytes() == before


def test_scope_isolation_and_revision_conflicts_preserve_content(database):
    store = WorkspaceGraphAuthority(database, "project", "workspace")
    database.execute("BEGIN IMMEDIATE")
    first = store.enroll(EMPTY)
    assert WorkspaceGraphAuthority(database, "other", "workspace").read() is None
    assert WorkspaceGraphAuthority(database, "project", "other").read() is None
    with pytest.raises(ValueError, match="already enrolled"):
        store.enroll(GRAPH)
    for revision in (0, True, 2):
        with pytest.raises(ValueError):
            store.write(GRAPH, revision)
    assert store.read() == first
    store.write(GRAPH)
    database.rollback()
    assert store.read() is None


@pytest.mark.parametrize("column,value", [("graph", "not json"), ("graph", '{}'), ("graph", '1'),
                                         ("graph", '{"nodes":[{}],"edges":[]}'),
                                         ("graph", json.dumps(GRAPH)), ("digest", "wrong")])
def test_corrupt_authority_never_falls_back_or_overwrites(database, column, value):
    store = WorkspaceGraphAuthority(database, "project", "workspace")
    database.execute("BEGIN IMMEDIATE")
    store.enroll(EMPTY)
    database.execute(f"UPDATE workspace_graph_authority SET {column}=?", (value,))
    for operation in (store.read, store.enrolled, lambda: store.enroll(EMPTY), lambda: store.write(EMPTY)):
        with pytest.raises(ValueError, match="corrupt"):
            operation()


@pytest.mark.parametrize("graph", [{"nodes": [], "edges": [], "extra": 1},
                                   {"nodes": [{"id": "x"}, {"id": "x"}], "edges": []},
                                   {"nodes": [{"id": "x", "x": float("nan")}], "edges": []}])
def test_noncanonical_or_invalid_input_cannot_enroll(database, graph):
    database.execute("BEGIN IMMEDIATE")
    store = WorkspaceGraphAuthority(database, "project", "workspace")
    with pytest.raises(ValueError):
        store.enroll(graph)
    assert not store.enrolled()


def test_invalid_scope_rejected(database):
    with pytest.raises(ValueError, match="scope"):
        WorkspaceGraphAuthority(database, "../project", "workspace")
