"""Strict scoped review chains, replay, CAS, immutable records and hard bounds."""
import json
import sqlite3

import pytest

from database.repositories import opora_proposal_review_records as records
from database.repositories import opora_proposal_reviews as reviews
from database.schema.project_initialization import initialize_project_schema


def policy(parent=None, **updates):
    return {"schemaVersion": 1, "kind": "acceptance-policy", "project": "p", "workspace": "w",
        "parentPolicyRevision": parent, "enabled": True, "rules": {"requireAcknowledgementFrom": "elevated", "blockOpenFindings": True},
        "by": {"kind": "human", "name": "Reviewer"}, "createdAt": "2026-10-21T12:00:00Z", **updates}


def event(parent=None, key="first", **updates):
    return {"schemaVersion": 1, "kind": "proposal-review-event", "project": "p", "workspace": "w",
        "proposalKind": "content", "proposalId": "a" * 40, "parentReviewEvent": parent, "idempotencyKey": key,
        "type": "comment", "message": "Review this value", "anchor": "/changes/0/value",
        "by": {"kind": "agent", "name": "Worker"}, "createdAt": "2026-10-21T12:00:00Z", **updates}


def receipt(**updates):
    return {"schemaVersion": 1, "kind": "acceptance-receipt", "project": "p", "workspace": "w",
        "acceptedRevision": "b" * 40, "proposalKind": "content", "proposalId": "a" * 40, "policyId": "c" * 40,
        "risk": "elevated", "reasons": ["Rules changed"], "reviewHead": None, "ackId": None, "bootstrap": False,
        "by": {"kind": "human", "name": "Reviewer"}, "createdAt": "2026-10-21T12:00:00Z", **updates}


@pytest.fixture
def db():
    connection = sqlite3.connect(":memory:")
    initialize_project_schema(connection)
    connection.commit()
    yield connection
    connection.close()


def test_policy_cas_historical_scope_and_transaction_ownership(db):
    repo = reviews.AcceptancePolicies(db, "p", "w")
    with pytest.raises(RuntimeError):
        repo.configure(policy(), None)
    db.execute("BEGIN IMMEDIATE")
    first = repo.configure(policy(), None)
    second = repo.configure(policy(first["id"], enabled=False), first["id"])
    assert repo.head() == second["id"] and repo.read(first["id"])["enabled"]
    with pytest.raises(ValueError, match="CAS"):
        repo.configure(policy(), None)
    with pytest.raises(ValueError):
        reviews.AcceptancePolicies(db, "p", "other").read(first["id"])
    db.rollback()
    assert repo.head() is None


def test_event_idempotency_before_head_cas_and_foreign_proposal_rejection(db):
    db.execute("BEGIN IMMEDIATE")
    repo = reviews.ProposalReview(db, "p", "w", "content", "a" * 40)
    first = repo.append(event(), None)
    second = repo.append(event(first["id"], "second"), first["id"])
    retry = event(createdAt="2026-10-22T12:00:00Z")
    assert repo.append(retry, None) == first == repo.replay("first")
    assert repo.head() == second["id"] and repo.events() == [first, second]
    with pytest.raises(ValueError, match="idempotency"):
        repo.append(event(message="Different"), None)
    with pytest.raises(ValueError, match="idempotency"):
        repo.append(event(by={"kind": "agent", "name": "Other worker"}), None)
    with pytest.raises(ValueError, match="CAS"):
        repo.append(event(key="stale"), None)
    with pytest.raises(ValueError, match="foreign"):
        reviews.ProposalReview(db, "p", "w", "spec", "a" * 40).read(first["id"])


def test_human_ack_binds_risk_digest_policy_and_exact_preceding_head(db):
    db.execute("BEGIN IMMEDIATE")
    repo = reviews.ProposalReview(db, "p", "w", "content", "a" * 40)
    finding = repo.append(event(type="finding", severity="blocking"), None)
    base = {key: value for key, value in event(finding["id"], "ack").items() if key not in {"message", "anchor"}}
    ack = {**base, "type": "ack", "by": {"kind": "human", "name": "Reviewer"}, "policyId": "c" * 40,
           "risk": "elevated", "riskDigest": "d" * 64, "parentAcceptedHead": "e" * 40, "reviewHead": finding["id"]}
    result = repo.append(ack, finding["id"])
    assert repo.read(result["id"])["riskDigest"] == "d" * 64
    for patch in ({"riskDigest": "bad"}, {"reviewHead": None}, {"by": {"kind": "agent", "name": "Worker"}}):
        with pytest.raises(ValueError):
            repo.append({**ack, **patch}, finding["id"])


@pytest.mark.parametrize("target", ["policy", "event", "receipt"])
def test_immutable_sql_records_and_references_reject_replace_recursive_off(db, target):
    db.execute("BEGIN IMMEDIATE")
    if target == "policy":
        reviews.AcceptancePolicies(db, "p", "w").configure(policy(), None)
        table, ref = "opora_acceptance_policies", "opora_acceptance_policy_refs"
    elif target == "event":
        reviews.ProposalReview(db, "p", "w", "content", "a" * 40).append(event(), None)
        table, ref = "opora_proposal_review_events", "opora_proposal_review_refs"
    else:
        reviews.AcceptanceReceipts(db, "p", "w").insert(receipt())
        table, ref = "opora_acceptance_receipts", None
    db.execute("PRAGMA recursive_triggers=OFF")
    for sql in (f"UPDATE {table} SET content='{{}}'", f"DELETE FROM {table}", f"INSERT OR REPLACE INTO {table} SELECT * FROM {table}"):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(sql)
    if ref:
        for sql in (f"DELETE FROM {ref}", f"INSERT OR REPLACE INTO {ref} SELECT * FROM {ref}"):
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(sql)


@pytest.mark.parametrize("change", [{"enabled": 1}, {"schemaVersion": True}, {"by": {"kind": "agent", "name": "Worker"}},
    {"rules": {"requireAcknowledgementFrom": "critical", "blockOpenFindings": 0}}])
def test_policy_strict_boolean_and_actor_types(db, change):
    db.execute("BEGIN IMMEDIATE")
    with pytest.raises(ValueError):
        reviews.AcceptancePolicies(db, "p", "w").configure(policy(**change), None)


def test_corrupt_json_scope_hash_and_deep_input_fail_closed(db):
    db.execute("BEGIN IMMEDIATE")
    repo = reviews.AcceptancePolicies(db, "p", "w")
    original = repo.configure(policy(), None)
    db.execute("DROP TRIGGER opora_acceptance_policies_update")
    for changed in ({**original, "enabled": False}, {**original, "workspace": "other"}):
        db.execute("UPDATE opora_acceptance_policies SET content=?", (json.dumps(changed),))
        with pytest.raises(ValueError):
            repo.read(original["id"])
    raw = '{"schemaVersion":1,' + json.dumps(original)[1:]
    db.execute("UPDATE opora_acceptance_policies SET content=?", (raw,))
    with pytest.raises(ValueError, match="Duplicate"):
        repo.read(original["id"])
    nested = []
    for _ in range(66):
        nested = [nested]
    with pytest.raises(ValueError):
        reviews.ProposalReview(db, "p", "w", "content", "a" * 40).append(event(message=nested), None)


def test_hard_bounds_and_receipt_replay_do_not_refund_or_truncate(db, monkeypatch):
    db.execute("BEGIN IMMEDIATE")
    policies = reviews.AcceptancePolicies(db, "p", "w")
    first = policies.configure(policy(), None)
    monkeypatch.setattr(reviews, "MAX_POLICIES", 1)
    with pytest.raises(ValueError, match="bound"):
        policies.configure(policy(first["id"]), first["id"])
    discussion = reviews.ProposalReview(db, "p", "w", "content", "a" * 40)
    monkeypatch.setattr(reviews, "MAX_EVENTS", 1)
    discussion.append(event(), None)
    with pytest.raises(ValueError, match="bound"):
        discussion.append(event(discussion.head(), "second"), discussion.head())
    with pytest.raises(ValueError):
        discussion.append(event(message="x" * 8001, key="large"), None)
    receipts = reviews.AcceptanceReceipts(db, "p", "w")
    stored = receipts.insert(receipt())
    monkeypatch.setattr(records, "PROJECT_LIMIT", 1)
    assert receipts.insert(receipt()) == stored
    with pytest.raises(ValueError, match="quota"):
        receipts.insert(receipt(acceptedRevision="f" * 40))
    assert len(discussion.events()) == 1 and policies.head() == first["id"]
    assert db.in_transaction
