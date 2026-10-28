"""Relace brány: tabulka vznikne s projektem, ukládá se jen otisk tokenu a zneplatnění platí jednou."""
import sqlite3

import pytest

from database.repositories.gate_sessions import GateSessionStore
from database.schema.project_initialization import initialize_project_schema


def session(**changes):
    return {"id": "gs_1", "project_id": "p1", "workspace_id": "main", "role": "worker", "worker_name": "dev",
            "worker_meta": {"office": "o1"}, "token_hash": "h" * 64, "created_at": "2026-10-28T10:00:00Z",
            "expires_at": "2026-10-28T18:00:00Z", **changes}


@pytest.fixture
def db():
    connection = sqlite3.connect(":memory:")
    initialize_project_schema(connection)
    yield connection
    connection.close()


def test_insert_get_and_lookup_by_hash(db):
    store = GateSessionStore(db)
    store.insert(session())
    row = store.get("gs_1")
    assert row["worker_meta"] == {"office": "o1"} and row["revoked_at"] is None
    assert store.by_hash("h" * 64)["id"] == "gs_1"
    assert store.by_hash("x" * 64) is None and store.get("gs_2") is None


def test_role_is_checked_and_hash_is_unique(db):
    store = GateSessionStore(db)
    with pytest.raises(sqlite3.IntegrityError):
        store.insert(session(role="human"))
    store.insert(session())
    with pytest.raises(sqlite3.IntegrityError):
        store.insert(session(id="gs_2"))


def test_revoke_happens_once(db):
    store = GateSessionStore(db)
    store.insert(session())
    assert store.revoke("gs_1", "2026-10-28T11:00:00Z") is True
    assert store.revoke("gs_1", "2026-10-28T12:00:00Z") is False
    assert store.get("gs_1")["revoked_at"] == "2026-10-28T11:00:00Z"
