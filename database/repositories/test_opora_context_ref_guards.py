"""Opt-in SQL reference guards prevent invisible accepted-head rewind and ABA."""
import hashlib
import sqlite3

import pytest

from database.repositories import opora_execution_contexts as private
from database.repositories.opora_changesets import ChangesetRepository
from database.schema.project_initialization import initialize_project_schema


def revision(db, project="p", workspace="w", parent=None, subject="Root"):
    repo = ChangesetRepository(db, project, workspace)
    return repo.insert({"project": project, "workspace": workspace,
        "kind": "acceptance" if parent else "baseline", "parentRevision": parent,
        "proposalId": hashlib.sha1(subject.encode(), usedforsecurity=False).hexdigest() if parent else None,
        "createdAt": "now", "subject": subject,
        "by": {"kind": "human", "name": "Fixture"}, "documents": []})["id"]


@pytest.fixture
def db():
    connection = sqlite3.connect(":memory:")
    initialize_project_schema(connection)
    connection.commit()
    connection.execute("BEGIN IMMEDIATE")
    yield connection
    connection.close()


def enrolled(db):
    origin = revision(db)
    ChangesetRepository(db, "p", "w").advance(None, origin)
    private.key(db, "p", create=True)
    return origin


def test_child_allows_forward_update_but_rewind_and_sibling_are_rejected(db):
    origin = enrolled(db)
    child = revision(db, parent=origin, subject="Child")
    sibling = revision(db, parent=origin, subject="Sibling")
    repo = ChangesetRepository(db, "p", "w")
    assert repo.read(child)["parentRevision"] == origin
    repo.advance(origin, child)
    for target in (origin, sibling, "0" * 40):
        with pytest.raises(sqlite3.IntegrityError, match="scoped child"):
            db.execute("UPDATE opora_spec_refs SET accepted_id=?", (target,))
    assert repo.head() == child


@pytest.mark.parametrize("sql", [
    "DELETE FROM opora_spec_refs",
    "INSERT OR REPLACE INTO opora_spec_refs SELECT * FROM opora_spec_refs",
    "UPDATE opora_spec_refs SET project_id='other'",
    "UPDATE opora_spec_refs SET workspace_id='other'",
])
def test_enrolled_delete_replace_and_identity_moves_reject_with_recursive_off(db, sql):
    origin = enrolled(db)
    db.execute("PRAGMA recursive_triggers=OFF")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(sql)
    assert ChangesetRepository(db, "p", "w").head() == origin


def test_move_from_unenrolled_into_enrolled_project_is_rejected(db):
    origin = revision(db, project="legacy")
    ChangesetRepository(db, "legacy", "w").advance(None, origin)
    private.key(db, "p", create=True)
    with pytest.raises(sqlite3.IntegrityError, match="identity"):
        db.execute("UPDATE opora_spec_refs SET project_id='p' WHERE project_id='legacy'")


def test_noop_and_transaction_rollback_preserve_original_head(db):
    origin = enrolled(db)
    db.execute("UPDATE opora_spec_refs SET accepted_id=accepted_id")
    db.commit()
    db.execute("BEGIN IMMEDIATE")
    child = revision(db, parent=origin)
    ChangesetRepository(db, "p", "w").advance(origin, child)
    db.rollback()
    assert ChangesetRepository(db, "p", "w").head() == origin


def test_new_workspace_root_allowed_but_nonroot_or_foreign_revision_denied(db):
    origin = enrolled(db)
    root = revision(db, workspace="new")
    child = revision(db, workspace="new", parent=root)
    with pytest.raises(sqlite3.IntegrityError, match="scoped root"):
        ChangesetRepository(db, "p", "new").advance(None, child)
    with pytest.raises(sqlite3.IntegrityError, match="scoped root"):
        ChangesetRepository(db, "p", "foreign").advance(None, origin)
    ChangesetRepository(db, "p", "new").advance(None, root)
    assert ChangesetRepository(db, "p", "new").read(root)["parentRevision"] is None


def test_legacy_unprepared_project_retains_reference_writes(db):
    origin = revision(db)
    repo = ChangesetRepository(db, "p", "w")
    repo.advance(None, origin)
    child = revision(db, parent=origin)
    repo.advance(origin, child)
    repo.advance(child, origin)
    db.execute("INSERT OR REPLACE INTO opora_spec_refs VALUES('p','w',?)", (origin,))
    db.execute("DELETE FROM opora_spec_refs")
    assert repo.head() is None


def test_registered_project_copy_preserves_advanced_ref_before_enrollment_key(db):
    from backend.canvas.migrate_to_project_folders import _copy_rows
    from database.schema.project_schema import PROJECT_TABLES

    origin = enrolled(db)
    child = revision(db, parent=origin)
    ChangesetRepository(db, "p", "w").advance(origin, child)
    target = sqlite3.connect(":memory:")
    try:
        initialize_project_schema(target)
        target.commit()
        order = list(PROJECT_TABLES)
        assert order.index("opora_spec_refs") < order.index("opora_execution_context_keys")
        for table, column in PROJECT_TABLES.items():
            _copy_rows(db, target, table, f"WHERE {column}=?", ("p",))
        repo = ChangesetRepository(target, "p", "w")
        assert repo.head() == child and repo.read(child)["parentRevision"] == origin
        assert private.key(target, "p") == private.key(db, "p")
        with pytest.raises(sqlite3.IntegrityError, match="scoped child"):
            repo.advance(child, origin)
    finally:
        target.close()
