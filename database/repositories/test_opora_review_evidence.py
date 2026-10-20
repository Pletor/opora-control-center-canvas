"""Immutable evidence content and indexes cannot be rewritten or crossed by scope."""
import json

import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.opora_review_evidence import OporaReviewEvidence
from backend.canvas.test_opora_review_fixtures import AGENT, Reader
from backend.canvas.test_opora_review_fixtures import (
    evidence_project as evidence_fixture,  # noqa: F401
)
from database.repositories.opora_review_evidence import ReviewEvidenceRepository


@pytest.mark.parametrize("mutation", ["content", "scope", "id", "index", "json"])
def test_corrupt_record_is_rejected(evidence_project, mutation):
    service, payload = evidence_project
    domain = OporaReviewEvidence(service, Reader(payload))
    record = domain.observe(payload, AGENT)["snapshot"]
    changed = dict(record)
    if mutation == "content":
        changed["complete"] = False
    elif mutation == "scope":
        changed["workspace"] = "other"
    elif mutation == "id":
        changed["id"] = "0" * 40
    db = service.db_for(payload["project"])
    with service.lock_for(payload["project"]), db:
        if mutation == "index":
            db.execute("UPDATE opora_review_evidence SET pr_number=2")
        else:
            db.execute("UPDATE opora_review_evidence SET content=?", ("broken" if mutation == "json" else json.dumps(changed),))
    with pytest.raises(ValueError):
        domain.read(payload["project"], payload["workspace"], record["id"])


def test_insert_requires_transaction_and_cannot_cross_scope(evidence_project):
    service, payload = evidence_project
    record = OporaReviewEvidence(service, Reader(payload)).observe(payload, AGENT)["snapshot"]
    content = {key: value for key, value in record.items() if key != "id"}
    repo = ReviewEvidenceRepository(service.db_for(payload["project"]), payload["project"], "other")
    with pytest.raises(RuntimeError):
        repo.insert(content)
    with service.lock_for(payload["project"]), repo.db:
        repo.db.execute("BEGIN IMMEDIATE")
        with pytest.raises(ValueError):
            repo.insert(content)
    assert repo.list() == []


def test_additive_schema_reopens_old_database_without_changing_accepted_revision(evidence_project):
    service, payload = evidence_project
    pid = payload["project"]
    with service.lock_for(pid), service.db_for(pid) as db:
        db.execute("DROP TABLE opora_review_evidence")
    service.close()
    reopened = CanvasService(service.root)
    try:
        value = OporaReviewEvidence(reopened).list(pid, payload["workspace"])
        assert value["acceptedHead"] == payload["expectedAcceptedHead"] and value["items"] == []
    finally:
        reopened.close()


