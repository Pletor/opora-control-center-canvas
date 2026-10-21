"""Private context persistence, rollback, strict JSON and origin protection."""
import hashlib
import sqlite3

import pytest

from database.repositories import opora_execution_contexts as contexts
from database.schema.project_initialization import initialize_project_schema


@pytest.fixture
def db():
    connection = sqlite3.connect(":memory:")
    initialize_project_schema(connection)
    connection.commit()
    yield connection
    connection.close()


def prepare(db):
    db.execute("BEGIN IMMEDIATE")
    contexts.key(db, "p", create=True)


def test_key_stable_reopen_and_transaction_rollback(tmp_path):
    path = tmp_path / "project.sqlite"
    db = sqlite3.connect(path)
    initialize_project_schema(db)
    db.commit()
    with pytest.raises(RuntimeError):
        contexts.key(db, "p", create=True)
    prepare(db)
    original = contexts.key(db, "p")
    assert len(bytes.fromhex(original)) == 32
    contexts.insert(db, "p", "w", "e", {"private": "secret"})
    db.commit()
    db.close()
    db = sqlite3.connect(path)
    initialize_project_schema(db)
    db.commit()
    assert contexts.key(db, "p") == original
    assert contexts.read(db, "p", "w", "e") == {"private": "secret"}
    db.execute("BEGIN IMMEDIATE")
    contexts.proof(db, "p", "w", "e", {"checked": "head"})
    db.rollback()
    assert contexts.read_proof(db, "p", "w", "e") is None
    db.close()


def test_pin_scope_immutable_origin_and_mutable_proof(db):
    prepare(db)
    pin = {"snapshot": {"credential": "never public"}, "ordered": [1, None, True]}
    contexts.insert(db, "p", "w", "e", pin)
    before = db.execute("SELECT pin_json,pin_digest FROM opora_execution_context_pins").fetchone()
    for sql in (
        "UPDATE opora_execution_context_pins SET workspace_id='elsewhere'",
        "UPDATE opora_execution_context_pins SET pin_json='{}'",
        "DELETE FROM opora_execution_context_pins",
        "INSERT OR REPLACE INTO opora_execution_context_pins SELECT * FROM opora_execution_context_pins",
        "UPDATE opora_execution_context_keys SET secret='broken'",
        "DELETE FROM opora_execution_context_keys",
        "INSERT OR REPLACE INTO opora_execution_context_keys SELECT * FROM opora_execution_context_keys",
    ):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(sql)
    with pytest.raises(ValueError, match="scope"):
        contexts.read(db, "p", "wrong", "e")
    contexts.proof(db, "p", "w", "e", {"checkedAcceptedRevision": "new"})
    assert contexts.read_proof(db, "p", "w", "e") == {"checkedAcceptedRevision": "new"}
    assert db.execute("SELECT pin_json,pin_digest FROM opora_execution_context_pins").fetchone() == before
    assert contexts.read(db, "p", "w", "e") == pin
    assert db.in_transaction


@pytest.mark.parametrize("value", [{"a": float("nan")}, {"a": float("inf")}, {1: "bad"}, {"a": ()}, []])
def test_strict_json_rejects_non_json(db, value):
    prepare(db)
    with pytest.raises(ValueError):
        contexts.insert(db, "p", "w", "e", value)


def test_bounds_and_project_quota_are_checked_before_write(db, monkeypatch):
    prepare(db)
    monkeypatch.setattr(contexts, "MAX_PIN", 30)
    monkeypatch.setattr(contexts, "PROJECT_LIMIT", 35)
    contexts.insert(db, "p", "w", "first", {"secret": "a" * 10})
    with pytest.raises(ValueError, match="size"):
        contexts.insert(db, "p", "w", "oversize", {"secret": "a" * 30})
    with pytest.raises(ValueError, match="quota"):
        contexts.insert(db, "p", "w", "second", {"secret": "a" * 10})
    with pytest.raises(ValueError, match="quota"):
        contexts.proof(db, "p", "w", "first", {"checked": "head"})
    assert db.execute("SELECT count(*) FROM opora_execution_context_pins").fetchone()[0] == 1
    assert contexts.read_proof(db, "p", "w", "first") is None
    monkeypatch.setattr(contexts, "MAX_PROOF", 5)
    with pytest.raises(ValueError, match="size"):
        contexts.proof(db, "p", "w", "first", {"checked": "head"})


def test_missing_or_malformed_key_never_regenerated(db):
    prepare(db)
    contexts.insert(db, "p", "w", "e", {})
    db.execute("DROP TRIGGER opora_private_context_key_delete")
    db.execute("DELETE FROM opora_execution_context_keys")
    with pytest.raises(ValueError, match="missing"):
        contexts.key(db, "p", create=True)
    db.execute("INSERT INTO opora_execution_context_keys VALUES('p','broken')")
    with pytest.raises(ValueError, match="Malformed"):
        contexts.key(db, "p", create=True)


@pytest.mark.parametrize("raw", ['{"x":1,"x":2}', '{"x":NaN}', '{"x": 1}', '[]'])
def test_stored_noncanonical_or_invalid_json_refused(db, raw):
    prepare(db)
    contexts.insert(db, "p", "w", "e", {})
    db.execute("DROP TRIGGER opora_private_context_pin_update")
    db.execute("UPDATE opora_execution_context_pins SET pin_json=?,pin_digest=?",
               (raw, hashlib.sha256(raw.encode()).hexdigest()))
    with pytest.raises(ValueError):
        contexts.read(db, "p", "w", "e")


def test_corrupt_digest_and_deep_json_fail_closed(db):
    prepare(db)
    contexts.insert(db, "p", "w", "e", {})
    db.execute("DROP TRIGGER opora_private_context_pin_update")
    db.execute("UPDATE opora_execution_context_pins SET pin_digest='wrong'")
    with pytest.raises(ValueError, match="integrity"):
        contexts.read(db, "p", "w", "e")
    value = {}
    for _ in range(66):
        value = {"nested": value}
    with pytest.raises(ValueError, match="complexity"):
        contexts.insert(db, "p", "w", "deep", value)


def test_writes_never_start_or_commit_transactions(db):
    with pytest.raises(RuntimeError):
        contexts.insert(db, "p", "w", "e", {})
    with pytest.raises(RuntimeError):
        contexts.proof(db, "p", "w", "e", {})
    prepare(db)
    contexts.insert(db, "p", "w", "e", {})
    db.rollback()
    assert db.execute("SELECT count(*) FROM opora_execution_context_keys").fetchone()[0] == 0
    assert db.execute("SELECT count(*) FROM opora_execution_context_pins").fetchone()[0] == 0
