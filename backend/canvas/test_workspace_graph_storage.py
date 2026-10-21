"""Graph and architecture writes share the caller's transaction."""
import sqlite3
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from backend.canvas.graph import EMPTY, encode
from backend.canvas.workspace_graph_storage import (
    authoritative_raw,
    refuse_authority_restore,
    save_authoritative,
)
from database.repositories.workspace_graph_authority import WorkspaceGraphAuthority
from database.schema.opora_execution_schema import SCHEMA as EXECUTION_SCHEMA
from database.schema.opora_graph_schema import SCHEMA as GRAPH_SCHEMA
from database.schema.opora_review_policy_schema import SCHEMA as POLICY_SCHEMA
from database.schema.workspace_graph_authority_schema import SCHEMA


@pytest.fixture
def service(tmp_path):
    db = sqlite3.connect(tmp_path / "project.sqlite")
    db.executescript(SCHEMA)
    db.executescript(EXECUTION_SCHEMA)
    db.executescript(GRAPH_SCHEMA)
    db.executescript(POLICY_SCHEMA)
    db.execute("CREATE TABLE opora_spec_refs(project_id,workspace_id,accepted_id)")
    db.execute("CREATE TABLE architecture(value)")
    service = SimpleNamespace(db_for=lambda pid: db, lock_for=lambda pid: nullcontext())
    service.architecture = SimpleNamespace(write=lambda db, *args: db.execute("INSERT INTO architecture VALUES('new')"))
    yield service
    db.close()


def save(service, commit=True):
    return save_authoritative(service, "p", "w", EMPTY, EMPTY, 0, True, "human", (set(), set()), commit=commit)


def enroll(service):
    db = service.db_for("p")
    db.execute("BEGIN IMMEDIATE")
    WorkspaceGraphAuthority(db, "p", "w").enroll(EMPTY)
    db.commit()
    return db


def test_unenrolled_scope_does_not_start_transaction_or_write(service):
    assert authoritative_raw(service, "p", "w") is None
    assert save(service) is False
    assert not service.db_for("p").in_transaction
    refuse_authority_restore(service.db_for("p"))


def test_enrolled_write_commits_graph_and_architecture_together(service):
    db = enroll(service)
    assert save(service) is True
    assert not db.in_transaction
    assert WorkspaceGraphAuthority(db, "p", "w").read()["revision"] == 2
    assert db.execute("SELECT value FROM architecture").fetchall() == [("new",)]
    assert authoritative_raw(service, "p", "w") == encode(EMPTY)
    with pytest.raises(ValueError, match="restore is unavailable"):
        refuse_authority_restore(db)


def test_outer_transaction_owns_commit_and_rollback(service):
    db = enroll(service)
    with pytest.raises(RuntimeError, match="existing transaction"):
        save(service, commit=False)
    db.execute("BEGIN IMMEDIATE")
    assert save(service, commit=False)
    assert db.in_transaction
    db.rollback()
    assert WorkspaceGraphAuthority(db, "p", "w").read()["revision"] == 1
    assert db.execute("SELECT value FROM architecture").fetchall() == []


def test_failed_graph_write_rolls_back_architecture(service, monkeypatch):
    db = enroll(service)

    def fail(*args):
        raise OSError("injected write failure")

    monkeypatch.setattr(WorkspaceGraphAuthority, "write", fail)
    with pytest.raises(OSError, match="injected"):
        save(service)
    assert not db.in_transaction
    assert WorkspaceGraphAuthority(db, "p", "w").read()["revision"] == 1
    assert db.execute("SELECT value FROM architecture").fetchall() == []


def test_execution_enrollment_alone_blocks_backup_restore(service):
    db = service.db_for("p")
    db.execute("INSERT INTO opora_execution_epochs VALUES('p','w','card',7)")
    db.commit()
    assert WorkspaceGraphAuthority(db, "p", "w").read() is None
    with pytest.raises(ValueError, match="after execution enrollment"):
        refuse_authority_restore(db)
    assert db.execute("SELECT epoch FROM opora_execution_epochs").fetchone()[0] == 7
