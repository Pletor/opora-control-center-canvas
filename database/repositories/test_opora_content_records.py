"""Bounded immutable content ledger, integrity and transaction ownership."""
import copy
import json
import sqlite3

import pytest

from backend.canvas.graph import digest
from backend.canvas.opora_content_validation import validate_entry, validate_record, validate_value
from backend.canvas.opora_hub_store import content_id
from database.repositories import opora_content_records as storage
from database.repositories.opora_changesets import ChangesetRepository
from database.schema.project_initialization import initialize_project_schema


def entry(**overrides):
    return {"kind": "text", "target": "card", "field": "text", "ownerWorkspace": "w", "value": "Original", "revision": 0, **overrides}


def manifest(**overrides):
    return {"schemaVersion": 1, "kind": "content-manifest", "project": "p", "workspace": "w", "entries": [entry()], **overrides}


def proposal(**overrides):
    base = [entry()]
    return {"schemaVersion": 1, "kind": "content-proposal", "project": "p", "workspace": "w",
        "parentRevision": "a" * 40, "graphDigest": "b" * 64, "subject": "Update text", "by": {"kind": "agent", "name": "Builder"},
        "createdAt": "2026-10-21T12:00:00Z", "supersedes": None, "requiresBaseContentAdoption": True,
        "baseContentDigest": digest(base), "baseContent": base,
        "changes": [{"kind": "text", "target": "card", "field": "text", "value": "Desired", "before": "Original",
                     "acceptedBefore": None, "observedOwner": "w", "observedRevision": 0, "observedRound": None}], **overrides}


@pytest.fixture
def db():
    connection = sqlite3.connect(":memory:")
    initialize_project_schema(connection)
    connection.commit()
    yield connection
    connection.close()


def test_insert_hash_idempotence_scope_and_no_implicit_commit(db):
    repo = storage.ContentRecords(db, "p", "w")
    with pytest.raises(RuntimeError):
        repo.insert(proposal())
    db.execute("BEGIN IMMEDIATE")
    record = repo.insert(proposal())
    assert record["id"] == content_id(proposal())
    assert repo.insert(proposal()) == record == repo.read(record["id"])
    assert repo.proposals() == [record]
    with pytest.raises(ValueError, match="scope"):
        storage.ContentRecords(db, "p", "other").read(record["id"])
    assert db.in_transaction
    db.rollback()
    assert repo.proposals() == []


@pytest.mark.parametrize("manifest_mode", [False, True])
def test_sql_guards_block_mutation_and_replace_without_recursive_triggers(db, manifest_mode):
    db.execute("BEGIN IMMEDIATE")
    repo = storage.ContentRecords(db, "p", "w")
    record = repo.insert(manifest() if manifest_mode else proposal(), manifest=manifest_mode)
    table = "opora_content_manifests" if manifest_mode else "opora_content_proposals"
    db.execute("PRAGMA recursive_triggers=OFF")
    for sql in (f"DELETE FROM {table}", f"UPDATE {table} SET content='{{}}'", f"INSERT OR REPLACE INTO {table} SELECT * FROM {table}"):
        with pytest.raises(sqlite3.IntegrityError, match="Immutable"):
            db.execute(sql)
    assert repo.read(record["id"], manifest=manifest_mode) == record


@pytest.mark.parametrize("mutation", ["hash", "scope", "duplicate", "invalid-json"])
def test_corrupt_stored_records_fail_closed(db, mutation):
    db.execute("BEGIN IMMEDIATE")
    repo = storage.ContentRecords(db, "p", "w")
    record = repo.insert(manifest(), manifest=True)
    db.execute("DROP TRIGGER opora_content_manifests_update")
    changed = copy.deepcopy(record)
    if mutation == "hash":
        changed["entries"][0]["value"] = "Changed"
    elif mutation == "scope":
        changed["workspace"] = "other"
    raw = json.dumps(changed)
    if mutation == "duplicate":
        raw = '{"schemaVersion":1,' + raw[1:]
    elif mutation == "invalid-json":
        raw = "not JSON"
    db.execute("UPDATE opora_content_manifests SET content=?", (raw,))
    with pytest.raises(ValueError):
        repo.read(record["id"], manifest=True)


def test_duplicate_unsorted_entries_and_change_bounds_reject():
    for entries in ([entry(), entry()], [entry(target="z"), entry(target="a")], [entry()] * 16385):
        with pytest.raises(ValueError):
            validate_record(manifest(entries=entries), manifest=True)
    for changes in ([], proposal()["changes"] * 129, proposal()["changes"] * 2):
        with pytest.raises(ValueError):
            validate_record(proposal(changes=changes))
    with pytest.raises(ValueError, match="digest"):
        validate_record(proposal(baseContentDigest="c" * 64))


def test_strict_entry_types_native_revision_and_progress_exclusion():
    for changed in (entry(revision=True), entry(value="x" * 64001), entry(value="bad\0text"),
                    entry(target=""), entry(extra="unknown"), entry(value=float("nan"))):
        with pytest.raises(ValueError):
            validate_entry(changed)
    validate_value("drawing", "scene", {"elements": []})
    with pytest.raises(ValueError):
        validate_value("drawing", "scene", {"elements": [], "files": {"bytes": "hidden"}})
    for field, value in (("actions", {}), ("downloadsUrl", "file:///secret"), ("materials", [{"id": "m"}]),
                         ("actions", None), ("rules", None), ("blocks", None), ("materials", None),
                         ("blocks", [{"id": "b", "state": {"status": "open"}, "todos": []}])):
        with pytest.raises(ValueError):
            validate_value("config", field, value)
    validate_value("config", "downloadsUrl", None)
    validate_value("config", "downloadsUrl", True)
    validate_value("config", "downloadsUrl", False)
    for value in ("https://example.test", "", 0, 1, []):
        with pytest.raises(ValueError):
            validate_value("config", "downloadsUrl", value)


def test_size_and_project_quota_reject_before_writing_and_replay_is_free(db, monkeypatch):
    db.execute("BEGIN IMMEDIATE")
    repo = storage.ContentRecords(db, "p", "w")
    monkeypatch.setattr(storage, "MANIFEST_LIMIT", 10)
    with pytest.raises(ValueError, match="byte bound"):
        repo.insert(manifest(), manifest=True)
    monkeypatch.setattr(storage, "MANIFEST_LIMIT", 8 * 1024 * 1024)
    record = repo.insert(manifest(), manifest=True)
    monkeypatch.setattr(storage, "PROJECT_LIMIT", 1)
    assert repo.insert(manifest(), manifest=True) == record
    with pytest.raises(ValueError, match="quota"):
        repo.insert(proposal())
    assert db.execute("SELECT count(*) FROM opora_content_proposals").fetchone()[0] == 0
    for value in (0, 101, True):
        with pytest.raises(ValueError):
            repo.proposals(value)


def test_accepted_index_resolves_valid_manifest_and_rejects_wrong_relation(db):
    db.execute("BEGIN IMMEDIATE")
    repo = storage.ContentRecords(db, "p", "w")
    proposed = repo.insert(proposal())
    accepted_manifest = repo.insert(manifest(), manifest=True)
    revisions = ChangesetRepository(db, "p", "w")
    record = revisions.insert({"project": "p", "workspace": "w", "kind": "acceptance", "parentRevision": "a" * 40,
        "proposalId": proposed["id"], "createdAt": "now", "documents": [], "contentManifestId": accepted_manifest["id"]})
    assert repo.accepted(proposed["id"]) == record["id"]
    assert repo.accepted("0" * 40) is None
