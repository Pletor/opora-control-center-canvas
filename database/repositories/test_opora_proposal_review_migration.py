"""Migration preserves every proposal-review ledger and scope reference."""
import sqlite3

import pytest

from backend.canvas.migrate_to_project_folders import _copy_rows
from backend.canvas.opora_context_restore import refuse_context_restore
from database.repositories.opora_proposal_reviews import (
    AcceptancePolicies,
    AcceptanceReceipts,
    ProposalReview,
)
from database.repositories.test_opora_proposal_reviews import event, policy, receipt
from database.schema.opora_proposal_review_schema import TABLES
from database.schema.project_initialization import initialize_project_schema
from database.schema.project_schema import PROJECT_TABLES


def test_registered_copy_preserves_advanced_refs_and_receipts(tmp_path):
    source, target = sqlite3.connect(":memory:"), sqlite3.connect(tmp_path / "project.sqlite")
    for db in (source, target):
        initialize_project_schema(db)
        db.commit()
    source.execute("BEGIN IMMEDIATE")
    policies = AcceptancePolicies(source, "p", "w")
    initial = policies.configure(policy(), None)
    current = policies.configure(policy(initial["id"]), initial["id"])
    review = ProposalReview(source, "p", "w", "content", "a" * 40)
    first = review.append(event(), None)
    latest = review.append(event(first["id"], "second"), first["id"])
    AcceptanceReceipts(source, "p", "w").insert(receipt())
    for table in TABLES:
        assert PROJECT_TABLES[table] == "project_id"
        _copy_rows(source, target, table, "WHERE project_id=?", ("p",))
        assert sorted(tuple(row) for row in source.execute(f"SELECT * FROM {table}")) == sorted(tuple(row) for row in target.execute(f"SELECT * FROM {table}"))
    target.commit()
    target.close()
    target = sqlite3.connect(tmp_path / "project.sqlite")
    initialize_project_schema(target)
    assert AcceptancePolicies(target, "p", "w").head() == current["id"]
    assert ProposalReview(target, "p", "w", "content", "a" * 40).events() == [first, latest]
    assert AcceptanceReceipts(target, "p", "w").read("b" * 40) is not None
    with pytest.raises(ValueError, match="restore"):
        refuse_context_restore(target)
    source.close()
    target.close()


def test_bootstrap_receipt_is_distinct_and_cannot_acknowledge_a_proposal():
    db = sqlite3.connect(":memory:")
    initialize_project_schema(db)
    db.commit()
    db.execute("BEGIN IMMEDIATE")
    repo = AcceptanceReceipts(db, "p", "w")
    item = receipt(bootstrap=True, proposalKind=None, proposalId=None)
    assert repo.insert(item)["bootstrap"] is True
    with pytest.raises(ValueError):
        repo.insert({**item, "acceptedRevision": "d" * 40, "ackId": "f" * 40})
    db.close()
