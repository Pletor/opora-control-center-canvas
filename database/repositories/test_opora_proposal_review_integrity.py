"""Additional raw-writer and byte-bound regressions for proposal-review storage."""
import sqlite3

import pytest

from backend.canvas.opora_context_restore import refuse_context_restore
from database.repositories import opora_proposal_review_records as records
from database.repositories.opora_proposal_reviews import (
    AcceptancePolicies,
    AcceptanceReceipts,
    ProposalReview,
)
from database.repositories.test_opora_proposal_reviews import event, policy, receipt
from database.schema.project_initialization import initialize_project_schema


@pytest.fixture
def db():
    connection = sqlite3.connect(":memory:")
    initialize_project_schema(connection)
    connection.commit()
    connection.execute("BEGIN IMMEDIATE")
    yield connection
    connection.close()


def test_sql_policy_and_event_refs_cannot_rewind_but_noop_is_allowed(db):
    policies = AcceptancePolicies(db, "p", "w")
    first = policies.configure(policy(), None)
    second = policies.configure(policy(first["id"]), first["id"])
    with pytest.raises(sqlite3.IntegrityError, match="scoped child"):
        db.execute("UPDATE opora_acceptance_policy_refs SET policy_id=?", (first["id"],))
    db.execute("UPDATE opora_acceptance_policy_refs SET policy_id=policy_id")
    assert policies.head() == second["id"]
    review = ProposalReview(db, "p", "w", "content", "a" * 40)
    old = review.append(event(), None)
    new = review.append(event(old["id"], "next"), old["id"])
    with pytest.raises(sqlite3.IntegrityError, match="scoped child"):
        db.execute("UPDATE opora_proposal_review_refs SET head_id=?", (old["id"],))
    assert review.head() == new["id"]


def test_unique_idempotency_replace_cannot_erase_old_event_with_new_id(db):
    review = ProposalReview(db, "p", "w", "content", "a" * 40)
    first = review.append(event(), None)
    db.execute("PRAGMA recursive_triggers=OFF")
    with pytest.raises(sqlite3.IntegrityError, match="Immutable"):
        db.execute("INSERT OR REPLACE INTO opora_proposal_review_events SELECT project_id,workspace_id,proposal_kind,proposal_id,?,parent_id,idempotency_key,content FROM opora_proposal_review_events",
                   ("f" * 40,))
    assert review.events() == [first]


def test_resolve_requires_human_exact_target_resolution_and_reason(db):
    review = ProposalReview(db, "p", "w", "content", "a" * 40)
    finding = review.append(event(type="finding", severity="blocking"), None)
    base = {key: value for key, value in event(finding["id"], "resolve").items() if key not in {"message", "anchor"}}
    item = {**base, "by": {"kind": "human", "name": "Reviewer"}, "type": "resolve",
            "targetEventId": finding["id"], "resolution": "accepted", "reason": "Explicitly accepted known risk"}
    for patch in ({"by": {"kind": "agent", "name": "Worker"}}, {"reason": ""}, {"targetEventId": "unknown"}, {"resolution": "ignored"}):
        with pytest.raises(ValueError):
            review.append({**item, **patch}, finding["id"])
    assert review.append(item, finding["id"])["targetEventId"] == finding["id"]


def test_policy_event_and_receipt_bytes_are_bounded_before_insertion(db, monkeypatch):
    policies = AcceptancePolicies(db, "p", "w")
    review = ProposalReview(db, "p", "w", "content", "a" * 40)
    receipts = AcceptanceReceipts(db, "p", "w")
    for table, write in (("opora_acceptance_policies", lambda: policies.configure(policy(), None)),
                         ("opora_proposal_review_events", lambda: review.append(event(), None)),
                         ("opora_acceptance_receipts", lambda: receipts.insert(receipt()))):
        original = records.LIMITS[table]
        monkeypatch.setitem(records.LIMITS, table, 10)
        with pytest.raises(ValueError, match="byte limit"):
            write()
        assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
        monkeypatch.setitem(records.LIMITS, table, original)


def test_orphaned_reference_alone_refuses_restore_and_cannot_be_repaired(db):
    db.execute("INSERT INTO opora_acceptance_policy_refs VALUES('p','w',?)", ("a" * 40,))
    with pytest.raises(ValueError, match="missing"):
        AcceptancePolicies(db, "p", "w").head()
    with pytest.raises(ValueError, match="restore"):
        refuse_context_restore(db)
