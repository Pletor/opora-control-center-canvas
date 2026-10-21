"""Real durable attempts revoke stale success across failures and network races."""
from copy import deepcopy

import pytest

from backend.canvas.opora_review_evidence import OporaReviewEvidence
from backend.canvas.opora_review_observation_attempt import PolicyObservation, stamp
from backend.canvas.opora_review_policy_observation import policy_evaluation
from backend.canvas.opora_review_scope import context
from backend.canvas.test_opora_review_fixtures import AGENT, HUMAN, Reader
from backend.canvas.test_opora_review_fixtures import (
    evidence_project as evidence_fixture,  # noqa: F401
)
from backend.integrations.github_review_transport import GitHubReadError
from database.repositories.opora_review_attempts import Attempts
from database.repositories.opora_review_policy import Policies
from database.schema.opora_review_policy_schema import SCHEMA


@pytest.fixture
def configured(evidence_project):
    service, payload = evidence_project
    db = service.db_for(payload["project"])
    db.executescript(SCHEMA)
    reader = Reader(payload)
    reader.result["pr"].update(baseSha="f" * 40, state="open", draft=False)
    evidence = OporaReviewEvidence(service, reader)
    domain = PolicyObservation(evidence)
    initial = domain.observe(payload, AGENT)
    repo = Policies(db, payload["project"], payload["workspace"])
    with db:
        db.execute("BEGIN IMMEDIATE")
        policy = repo.activate({"schemaVersion": 1, "kind": "review-policy", "project": payload["project"],
            "workspace": payload["workspace"], "enabled": True, "parentPolicyRevision": None,
            "repository": {"id": 10, "fullName": "owner/repo", "baseBranch": "main"},
            "identityEvidenceId": initial["snapshot"]["id"], "by": HUMAN, "createdAt": stamp(),
            "rules": {"requiredChecks": [{"appId": 8, "name": "tests"}], "reviewerIds": [2],
                      "minimumCodeApprovals": 1, "minimumPlanApprovals": 1, "maxObservationAgeSeconds": 60}}, None)
    return service, payload, reader, domain, policy


def status(service, payload):
    pid, wid = payload["project"], payload["workspace"]
    with service.graph_lock_for(pid), service.lock_for(pid):
        return policy_evaluation(service, pid, wid, payload["prNumber"], context(service, pid, wid))


def test_activation_requires_refresh_then_failure_invalidates_success(configured):
    service, payload, reader, domain, _policy = configured
    assert status(service, payload)["status"] == "unknown"
    first = domain.observe(payload, AGENT)
    assert first["policyEvaluation"]["status"] == "satisfied"

    def failure():
        assert status(service, payload)["status"] == "unknown"
        raise GitHubReadError("secret-token-must-not-be-stored")

    reader.before_read = failure
    failed = domain.observe(payload, AGENT)
    assert failed["policyEvaluation"]["status"] == "unknown"
    assert "secret-token" not in str(failed)
    assert status(service, payload)["status"] == "unknown"
    assert domain.evidence.repository(payload["project"], payload["workspace"]).read(first["snapshot"]["id"]) == first["snapshot"]


def test_newer_started_attempt_wins_even_when_older_finishes_last(configured):
    service, payload, reader, domain, _policy = configured
    nested = []

    def second():
        reader.before_read = lambda: None
        nested.append(domain.observe(payload, AGENT))

    reader.before_read = second
    older = domain.observe(payload, AGENT)
    assert older["policyEvaluation"]["status"] == "unknown"
    assert status(service, payload)["evidenceId"] == nested[0]["snapshot"]["id"]
    assert status(service, payload)["status"] == "satisfied"


def test_mismatched_expected_sha_records_terminal_attempt_and_revokes_old_success(configured):
    service, payload, _reader, domain, _policy = configured
    assert domain.observe(payload, AGENT)["policyEvaluation"]["status"] == "satisfied"
    with pytest.raises(ValueError, match="SHA"):
        domain.observe({**payload, "expectedHeadSha": "0" * 40}, AGENT)
    assert status(service, payload)["status"] == "unknown"
    attempts = Attempts(service.db_for(payload["project"]), payload["project"], payload["workspace"])
    latest = attempts.latest(1, {"repository": "owner/repo", "branch": "main"})
    assert latest["state"] == "context_changed"


def test_policy_change_during_network_requires_new_observation(configured):
    service, payload, reader, domain, policy = configured

    def change():
        db = service.db_for(payload["project"])
        content = {key: value for key, value in deepcopy(policy).items() if key != "id"}
        content.update(parentPolicyRevision=policy["id"], createdAt=stamp())
        content["rules"]["maxObservationAgeSeconds"] = 90
        with db:
            db.execute("BEGIN IMMEDIATE")
            Policies(db, payload["project"], payload["workspace"]).activate(content, policy["id"])

    reader.before_read = change
    with pytest.raises(ValueError, match="policy changed"):
        domain.observe(payload, AGENT)
    assert status(service, payload)["status"] == "unknown"
    reader.before_read = lambda: None
    assert domain.observe(payload, AGENT)["policyEvaluation"]["status"] == "satisfied"


def test_unexpected_crash_leaves_durable_pending_and_no_fallback(configured):
    service, payload, reader, domain, _policy = configured
    domain.observe(payload, AGENT)

    def crash():
        raise RuntimeError("simulated process failure")

    reader.before_read = crash
    with pytest.raises(RuntimeError):
        domain.observe(payload, AGENT)
    assert status(service, payload)["status"] == "unknown"
    assert not service.db_for(payload["project"]).in_transaction


def test_accepted_head_race_finishes_attempt_without_storing_success(configured):
    service, payload, reader, domain, _policy = configured
    db = service.db_for(payload["project"])
    before = domain.evidence.repository(payload["project"], payload["workspace"]).list()

    def change():
        with db:
            db.execute("UPDATE opora_spec_refs SET accepted_id=?", ("0" * 40,))

    reader.before_read = change
    with pytest.raises(ValueError):
        domain.observe(payload, AGENT)
    assert domain.evidence.repository(payload["project"], payload["workspace"]).list() == before
    latest = Attempts(db, payload["project"], payload["workspace"]).latest(1, {"repository": "owner/repo", "branch": "main"})
    assert latest["state"] == "context_changed"


def test_historical_list_evaluation_reuses_policy_and_latest_attempt_reads(configured, monkeypatch):
    service, payload, _reader, domain, _policy = configured
    first = domain.observe(payload, AGENT)["snapshot"]
    second = domain.observe(payload, AGENT)["snapshot"]
    calls = []
    original = Attempts.latest

    def counted(self, *args):
        calls.append(args)
        return original(self, *args)

    monkeypatch.setattr(Attempts, "latest", counted)
    pid, wid = payload["project"], payload["workspace"]
    with service.graph_lock_for(pid), service.lock_for(pid):
        current, cache = context(service, pid, wid), {}
        old = policy_evaluation(service, pid, wid, 1, current, first, cache)
        new = policy_evaluation(service, pid, wid, 1, current, second, cache)
    assert len(calls) == 1
    assert old["status"] == "unknown" and new["status"] == "satisfied"
