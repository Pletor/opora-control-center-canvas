"""Ledger and global reservation invariants use real SQLite and caller rollback."""
import copy
import sqlite3

import pytest

from backend.canvas.opora_context_restore import refuse_context_restore
from backend.canvas.opora_execution_observer_validation import advance, observation
from backend.canvas.opora_hub_store import canonical
from backend.canvas.test_opora_execution_observers import observation as observed
from database.repositories import opora_execution_observer_sessions as sessions
from database.repositories import opora_execution_observers as storage
from database.schema.opora_execution_observer_schema import REGISTRY_SCHEMA, SCHEMA, TABLES
from database.schema.project_schema import PROJECT_SCHEMA, PROJECT_TABLES

STAMP = "2026-01-01T00:00:00+00:00"


def payload():
    return {"project": "draft", "workspace": "draft", "requestId": "intent", "executionId": "a" * 32,
            "nodeId": "node", "epoch": 1, "acceptedRevision": "b" * 40, "assignmentDigest": "c" * 64,
            "contextProtocolVersion": 1, "contextVersion": "d" * 64, "executionProtocolVersion": 2,
            "budget": {"policyHead": "e" * 40, "familyId": "f" * 40, "allocationId": "a" * 40,
                       "attempt": 1, "repairRound": 0, "kind": "initial", "admittedAt": 1000.25,
                       "runDeadlineAt": 1060.25, "maxRunSeconds": 60}, "authorityDeadlineAt": 1060.25,
            "provider": "anthropic-managed-agents", "repository": {"url": "https://github.com/example/repo", "commitSha": "1" * 40},
            "agentId": "agent", "agentVersion": 1, "environmentId": "env", "environmentDigest": "2" * 64,
            "configurationDigest": "3" * 64, "maxListCostCents": "100"}


@pytest.fixture
def ledger(tmp_path):
    db = sqlite3.connect(tmp_path / "project.sqlite")
    db.executescript(PROJECT_SCHEMA)
    yield db, storage.ObserverRecords(db, "draft", "draft")
    db.close()


def test_caller_rollback_hash_scope_and_reopen(ledger):
    db, repo = ledger
    db.execute("BEGIN")
    record = repo.insert(payload(), "broker", STAMP)
    assert len(record["id"]) == 40
    assert record["authorityDeadlineAt"] == 1060.25
    assert repo.insert(payload(), "broker", "2026-01-02T00:00:00+00:00") == record
    db.rollback()
    assert repo.intents() == []
    with pytest.raises(RuntimeError):
        repo.insert(payload(), "broker", STAMP)
    with db:
        db.execute("BEGIN")
        record = repo.insert(payload(), "broker", STAMP)
    other = sqlite3.connect(db.execute("PRAGMA database_list").fetchone()[2])
    assert storage.ObserverRecords(other, "draft", "draft").read(record["id"]) == record
    with pytest.raises(ValueError):
        storage.ObserverRecords(other, "draft", "other").read(record["id"])
    other.close()


def test_sql_guards_cas_rewind_replace_restore_and_migration_map(ledger):
    db, repo = ledger
    with db:
        db.execute("BEGIN")
        bound = repo.insert(payload(), "broker", STAMP)
        first_body = observed(bound)
        first = repo.insert(first_body, "broker", STAMP, observed=True)
        next_body = observed(bound, requestId="two", sequence=2, expectedObservationHead=first["id"])
        second = repo.insert(next_body, "broker", STAMP, observed=True)
        assert repo.insert(first_body, "broker", STAMP, observed=True) == first
        assert repo.head(bound["id"]) == second
        with pytest.raises(ValueError, match="backup restore"):
            refuse_context_restore(db)
        for table in TABLES:
            assert PROJECT_TABLES[table] == "project_id"
            for command in (f"DELETE FROM {table}", f"UPDATE {table} SET project_id='other'",
                            f"INSERT OR REPLACE INTO {table} SELECT * FROM {table}"):
                with pytest.raises(sqlite3.IntegrityError):
                    db.execute(command)
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE opora_execution_observation_refs SET head_id=?", (first["id"],))
        db.execute("UPDATE opora_execution_observation_refs SET head_id=head_id")
    db.executescript(SCHEMA)
    assert repo.read(bound["id"]) == bound and repo.head(bound["id"]) == second


def test_project_quota_replay_does_not_consume_bytes(ledger, monkeypatch):
    db, repo = ledger
    with db:
        db.execute("BEGIN")
        bound = repo.insert(payload(), "broker", STAMP)
        monkeypatch.setattr(storage, "PROJECT_LIMIT", 0)
        assert repo.insert(payload(), "broker", STAMP) == bound
        with pytest.raises(ValueError, match="quota"):
            repo.insert(observed(bound), "broker", STAMP, observed=True)
        with pytest.raises(ValueError, match="different content"):
            repo.insert({**payload(), "agentVersion": 2}, "broker", STAMP)


def test_read_refuses_tampered_normalized_record_and_index(ledger):
    db, repo = ledger
    with db:
        db.execute("BEGIN")
        bound = repo.insert(payload(), "broker", STAMP)
    db.execute("DROP TRIGGER opora_execution_intents_update")
    with db:
        db.execute("UPDATE opora_execution_intents SET content=?", (canonical({**bound, "agentVersion": 2}),))
    with pytest.raises(ValueError, match="integrity"):
        repo.read(bound["id"])
    with db:
        db.execute("UPDATE opora_execution_intents SET content=?,request_id='wrong'", (canonical(bound),))
    with pytest.raises(ValueError, match="index integrity"):
        repo.read(bound["id"])


def test_global_session_reservation_scope_uniqueness_immutability_and_quota(tmp_path, monkeypatch):
    db = sqlite3.connect(tmp_path / "registry.sqlite")
    db.executescript(REGISTRY_SCHEMA)
    with db:
        db.execute("BEGIN")
        sessions.reserve(db, "draft", "draft", "a" * 40, "session")
        sessions.reserve(db, "draft", "draft", "a" * 40, "session")
        with pytest.raises(ValueError):
            sessions.reserve(db, "other", "other", "b" * 40, "session")
        with pytest.raises(ValueError):
            sessions.reserve(db, "draft", "draft", "a" * 40, "another_session")
        monkeypatch.setattr(sessions, "MAX_RESERVATIONS", 1)
        with pytest.raises(ValueError, match="quota"):
            sessions.reserve(db, "draft", "draft", "b" * 40, "another_session")
        table = sessions.TABLE
        for command in (f"DELETE FROM {table}", f"UPDATE {table} SET project_id='other'",
                        f"INSERT OR REPLACE INTO {table} SELECT * FROM {table}"):
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(command)
    db.executescript(REGISTRY_SCHEMA)
    sessions.verify(db, "draft", "draft", "a" * 40, "session")
    with pytest.raises(ValueError):
        sessions.verify(db, "draft", "draft", "a" * 40, "missing")
    db.close()


@pytest.mark.parametrize("change", [
    {"sequence": 1}, {"sessionId": "other"}, {"observedAt": "2000-01-01T00:00:00+00:00"},
    {"cumulative": {"inputTokens": 0}}, {"cumulative": {"listCostCents": "0"}},
    {"cumulative": {"activeSeconds": 1}},
])
def test_cumulative_session_time_and_sequence_never_rewind(change):
    first = observed({"id": "a" * 40})
    second = {**copy.deepcopy(first), "sequence": 2, **change}
    if "cumulative" in change:
        second["cumulative"] = {**first["cumulative"], **change["cumulative"]}
    with pytest.raises(ValueError):
        advance(first, second)


@pytest.mark.parametrize("field,value", [("inputTokens", True), ("inputTokens", -1), ("activeSeconds", float("inf")),
    ("activeSeconds", True), ("listCostCents", "01"), ("currency", "EUR")])
def test_usage_strict_types(field, value):
    record = observed({"id": "a" * 40})
    record["cumulative"][field] = value
    with pytest.raises(ValueError):
        observation(record)


def test_legacy_migration_preserves_global_reservations(tmp_path):
    from backend.canvas.migrate_to_project_folders import migrate
    from database.schema.project_schema import REGISTRY_SCHEMA as ALL_REGISTRY_SCHEMA
    db = sqlite3.connect(tmp_path / "canvas.sqlite")
    db.executescript(ALL_REGISTRY_SCHEMA)
    with db:
        db.execute("BEGIN")
        sessions.reserve(db, "draft", "draft", "a" * 40, "session")
    expected = db.execute("SELECT * FROM opora_execution_observer_sessions").fetchall()
    db.close()
    result = migrate(tmp_path)
    assert result["registry"]["opora_execution_observer_sessions"] == 1
    with sqlite3.connect(tmp_path / "registry.sqlite") as copied:
        assert copied.execute("SELECT * FROM opora_execution_observer_sessions").fetchall() == expected
        sessions.verify(copied, "draft", "draft", "a" * 40, "session")
