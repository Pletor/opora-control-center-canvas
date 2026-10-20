"""Evidence never applies specifications and rejects races around network I/O."""
from copy import deepcopy

import pytest

from backend.canvas.opora_review_evidence import OporaReviewEvidence
from backend.canvas.test_opora_review_fixtures import AGENT, Reader, configure
from backend.canvas.test_opora_review_fixtures import (
    evidence_project as evidence_fixture,  # noqa: F401
)
from backend.integrations.github_review_transport import GitHubReadError


def test_observe_is_immutable_deduplicated_and_does_not_advance_accepted_plan(evidence_project):
    service, payload = evidence_project
    reader = Reader(payload)
    reader.before_read = lambda: assert_unlocked(service, payload["project"])
    domain = OporaReviewEvidence(service, reader)
    before = service.node_spec(payload["project"], payload["workspace"], "card")
    first = domain.observe(payload, AGENT)
    assert domain.observe(payload, AGENT) == first
    history = domain.list(payload["project"], payload["workspace"])
    assert history["acceptedHead"] == payload["expectedAcceptedHead"]
    assert len(history["items"]) == 1
    assert first["snapshot"]["initiatedBy"] == AGENT
    assert first["evaluation"]["planReview"]["status"] == "approved"
    assert service.node_spec(payload["project"], payload["workspace"], "card") == before
    assert domain.read(payload["project"], payload["workspace"], first["snapshot"]["id"]) == first


def assert_unlocked(service, pid):
    assert not service.graph_lock_for(pid)._is_owned()
    assert not service.lock_for(pid)._is_owned()
    assert not service.registry_lock._is_owned()


@pytest.mark.parametrize("kind", ["revision", "config", "readonly"])
def test_network_race_rejects_without_record(evidence_project, kind, monkeypatch):
    service, payload = evidence_project
    reader = Reader(payload)
    def change():
        pid = payload["project"]
        if kind == "revision":
            with service.lock_for(pid), service.db_for(pid) as db:
                db.execute("UPDATE opora_spec_refs SET accepted_id=?", ("0" * 40,))
        elif kind == "config":
            configure(service, pid, "https://github.com/owner/other")
        else:
            original = service.view
            monkeypatch.setattr(service, "view", lambda *args: {**original(*args), "readOnly": True})
    reader.before_read = change
    domain = OporaReviewEvidence(service, reader)
    with pytest.raises(ValueError):
        domain.observe(payload, AGENT)
    assert domain.repository(payload["project"], payload["workspace"]).list() == []


@pytest.mark.parametrize("kind", ["repository", "sha", "branch", "number"])
def test_remote_identity_mismatch_rejected_without_record(evidence_project, kind):
    service, payload = evidence_project
    reader = Reader(payload)
    if kind == "repository":
        reader.result["repository"]["fullName"] = "foreign/repo"
    elif kind == "sha":
        payload = {**payload, "expectedHeadSha": "b" * 40}
    elif kind == "branch":
        reader.result["pr"]["baseRef"] = "other"
    else:
        reader.result["pr"]["number"] = 2
    domain = OporaReviewEvidence(service, reader)
    with pytest.raises(ValueError):
        domain.observe(payload, AGENT)
    assert domain.repository(payload["project"], payload["workspace"]).list() == []


def test_failure_is_latest_unknown_attempt_and_keeps_historical_success(evidence_project):
    service, payload = evidence_project
    reader = Reader(payload)
    domain = OporaReviewEvidence(service, reader)
    initial = domain.observe(payload, AGENT)
    def fail():
        raise GitHubReadError("token=NEVER_PERSIST_THIS", status=403)
    reader.before_read = fail
    failed = domain.observe(payload, AGENT)
    assert failed["snapshot"]["complete"] is False
    assert "pr" not in failed["snapshot"] and "NEVER_PERSIST" not in str(failed)
    assert failed["evaluation"]["codeReview"]["status"] == "unknown"
    assert domain.list(payload["project"], payload["workspace"])["items"][0]["snapshot"]["id"] == failed["snapshot"]["id"]
    assert domain.read(payload["project"], payload["workspace"], initial["snapshot"]["id"])["snapshot"] == initial["snapshot"]


def test_later_head_sha_invalidates_old_success_without_mutating_snapshot(evidence_project):
    service, payload = evidence_project
    reader = Reader(payload)
    domain = OporaReviewEvidence(service, reader)
    first = domain.observe(payload, AGENT)
    immutable = deepcopy(first["snapshot"])
    reader.result["pr"]["headSha"] = "b" * 40
    reader.result["observedAt"] = "2026-10-20T13:00:00+00:00"
    domain.observe(payload, AGENT)
    old = domain.read(payload["project"], payload["workspace"], immutable["id"])
    assert old["snapshot"] == immutable
    assert old["evaluation"]["freshness"]["status"] == "stale"
    assert old["evaluation"]["codeReview"]["status"] == "unknown"


def test_local_project_reports_unavailable_and_bad_payload_never_calls_reader(evidence_project):
    service, payload = evidence_project
    reader = Reader(payload)
    domain = OporaReviewEvidence(service, reader)
    local = domain.list("draft", "draft")
    assert not local["available"] and local["repository"] is None
    for bad in ({**payload, "verdict": "approved"}, {**payload, "expectedAcceptedHead": "0" * 40},
                {**payload, "prNumber": True}, {**payload, "expectedHeadSha": "bad"}):
        with pytest.raises(ValueError):
            domain.observe(bad, AGENT)
    assert not reader.calls


def test_corrupted_accepted_reference_cannot_acquire_evidence(evidence_project):
    service, payload = evidence_project
    pid = payload["project"]
    with service.lock_for(pid), service.db_for(pid) as db:
        db.execute("UPDATE opora_spec_refs SET accepted_id=?", ("0" * 40,))
    reader = Reader(payload)
    domain = OporaReviewEvidence(service, reader)
    with pytest.raises(ValueError):
        domain.observe({**payload, "expectedAcceptedHead": "0" * 40}, AGENT)
    assert not reader.calls
    assert domain.repository(pid, payload["workspace"]).list() == []


def test_changed_configured_branch_invalidates_historical_approval(evidence_project):
    service, payload = evidence_project
    domain = OporaReviewEvidence(service, Reader(payload))
    first = domain.observe(payload, AGENT)
    configure(service, payload["project"], branch="release")
    old = domain.read(payload["project"], payload["workspace"], first["snapshot"]["id"])
    assert old["snapshot"] == first["snapshot"]
    assert old["evaluation"]["codeReview"]["status"] == "unknown"
    assert "repository-configuration-changed" in old["evaluation"]["blockers"]




def test_readonly_or_missing_accepted_baseline_never_calls_github(evidence_project):
    service, payload = evidence_project
    reader = Reader(payload)
    domain = OporaReviewEvidence(service, reader)
    with pytest.raises(ValueError):
        domain.observe({**payload, "workspace": "main"}, AGENT)
    with service.lock_for(payload["project"]), service.db_for(payload["project"]) as db:
        db.execute("DELETE FROM opora_spec_refs")
    with pytest.raises(ValueError):
        domain.observe(payload, AGENT)
    assert reader.calls == []


def test_write_failure_rolls_back_whole_observation(evidence_project, monkeypatch):
    from database.repositories.opora_review_evidence import ReviewEvidenceRepository
    service, payload = evidence_project
    domain = OporaReviewEvidence(service, Reader(payload))
    insert = ReviewEvidenceRepository.insert
    def fail_after_insert(self, content):
        insert(self, content)
        raise RuntimeError("injected rollback")
    monkeypatch.setattr(ReviewEvidenceRepository, "insert", fail_after_insert)
    with pytest.raises(RuntimeError, match="injected rollback"):
        domain.observe(payload, AGENT)
    assert domain.repository(payload["project"], payload["workspace"]).list() == []


@pytest.mark.parametrize("identity", ["repository", "pr"])
def test_recreated_remote_identity_invalidates_older_approval(evidence_project, identity):
    service, payload = evidence_project
    reader = Reader(payload)
    domain = OporaReviewEvidence(service, reader)
    first = domain.observe(payload, AGENT)
    reader.result[identity]["id"] += 1
    reader.result["observedAt"] = "2026-10-20T13:00:00+00:00"
    domain.observe(payload, AGENT)
    old = domain.read(payload["project"], payload["workspace"], first["snapshot"]["id"])
    assert old["evaluation"]["codeReview"]["status"] == "unknown"
    assert "github-repository-or-pr-identity-changed" in old["evaluation"]["blockers"]
