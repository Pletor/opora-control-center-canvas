"""Authority regressions exercise actual project SQLite and complete scoped evidence."""

import pytest

from backend.canvas.opora_reconciliation import OporaReconciliation
from backend.canvas.opora_review_evidence import OporaReviewEvidence
from backend.canvas.test_opora_review_fixtures import AGENT, HUMAN, Reader, configure
from backend.canvas.test_opora_review_fixtures import evidence_project as evidence_fixture
from database.repositories.opora_reconciliation_jobs import ReconciliationJobs
from database.schema.opora_reconciliation_jobs import JOB_SCHEMA
from database.schema.opora_reconciliation_schema import RECONCILIATION_SCHEMA

__all__ = ["evidence_fixture"]


@pytest.fixture
def reconciliation_project(evidence_project):
    service, payload = evidence_project
    service.db_for(payload["project"]).executescript(RECONCILIATION_SCHEMA + JOB_SCHEMA)
    reader = Reader(payload)
    reader.result["pr"].update(baseSha="f" * 40, state="open", draft=False)
    reader.result["repository"]["fullName"] = "Owner/Repo"
    evidence = OporaReviewEvidence(service, reader).observe(payload, AGENT)["snapshot"]
    scope = {key: payload[key] for key in ("project", "workspace")}
    return service, scope, {**scope, "expectedAcceptedHead": payload["expectedAcceptedHead"],
                            "identityEvidenceId": evidence["id"], "requestId": "enroll-1"}


def change(scope, generation, action, request):
    return {**scope, "expectedGeneration": generation, "action": action, "requestId": request}


def test_enrollment_replay_duplicate_pause_resume_cas(reconciliation_project):
    service, scope, payload = reconciliation_project
    authority = OporaReconciliation(service)
    first = authority.enroll(payload, HUMAN)
    bid = first["binding"]["id"]
    assert first["control"]["generation"] == 1
    assert authority.enroll(payload, HUMAN) == first
    assert first["binding"]["repository"] == {"id": 10, "fullName": "owner/repo", "baseBranch": "main"}
    with pytest.raises(ValueError, match="Pause"):
        authority.enroll({**payload, "requestId": "duplicate"}, HUMAN)
    with pytest.raises(ValueError, match="different"):
        authority.enroll({**payload, "expectedAcceptedHead": "b" * 40}, HUMAN)
    paused = authority.control(bid, change(scope, 1, "pause", "pause-1"), HUMAN)
    assert paused["job"]["state"] == "paused"
    assert authority.control(bid, change(scope, 1, "pause", "pause-1"), HUMAN) == paused
    with pytest.raises(ValueError, match="generation"):
        authority.control(bid, change(scope, 1, "resume", "stale"), HUMAN)
    resumed = authority.control(bid, change(scope, 2, "resume", "resume-1"), HUMAN)
    assert resumed["binding"] == first["binding"] and resumed["control"]["generation"] == 3
    row = authority.list(**scope, actor="human")["items"][0]
    assert row["job"]["state"] == "scheduled" and row["lastSuccessfulObservation"] is None
    assert "owner" not in row["job"] and "claimEpoch" not in row["job"]


@pytest.mark.parametrize("extra", [{"by": HUMAN}, {"repository": {"id": 42}}, {"merged": True}])
def test_spoofed_authority_fields_reject(reconciliation_project, extra):
    service, _, payload = reconciliation_project
    with pytest.raises(ValueError):
        OporaReconciliation(service).enroll({**payload, **extra}, HUMAN)


def test_exact_current_revision_and_scope_config_authority(reconciliation_project):
    service, scope, payload = reconciliation_project
    authority = OporaReconciliation(service)
    with pytest.raises(ValueError):
        authority.enroll(payload, AGENT)
    with pytest.raises(ValueError):
        authority.enroll({**payload, "workspace": "main"}, HUMAN)
    with pytest.raises(ValueError, match="revision changed"):
        authority.enroll({**payload, "expectedAcceptedHead": "a" * 40}, HUMAN)
    first = authority.enroll(payload, HUMAN)
    bid = first["binding"]["id"]
    authority.control(bid, change(scope, 1, "pause", "pause"), HUMAN)
    configure(service, scope["project"], branch="other")
    with pytest.raises(ValueError, match="configuration changed"):
        authority.control(bid, change(scope, 2, "resume", "resume"), HUMAN)
    assert authority.repository(**scope).latest_control(bid)["generation"] == 2


def test_atomic_rollback_when_job_creation_fails(reconciliation_project, monkeypatch):
    service, scope, payload = reconciliation_project
    authority = OporaReconciliation(service)
    def fail(*args):
        raise RuntimeError("injected durable job failure")
    monkeypatch.setattr(ReconciliationJobs, "create", fail)
    with pytest.raises(RuntimeError, match="injected"):
        authority.enroll(payload, HUMAN)
    assert authority.repository(**scope).bindings() == []
    assert service.db_for(scope["project"]).execute("SELECT COUNT(*) FROM opora_reconciliation_requests").fetchone()[0] == 0


def test_pause_remains_available_after_configuration_drift_or_readonly(reconciliation_project, monkeypatch):
    service, scope, payload = reconciliation_project
    authority = OporaReconciliation(service)
    first = authority.enroll(payload, HUMAN)
    original = service.view
    monkeypatch.setattr(service, "view", lambda *args: {**original(*args), "readOnly": True})
    monkeypatch.setenv("OPORA_RECONCILIATION_WORKER", "0")
    current = authority.list(**scope, actor="human")
    assert not current["canConfigure"] and current["canPause"]
    assert not current["automaticWorkerEnabled"] and current["automaticWorkerUnavailableReason"]
    paused = authority.control(first["binding"]["id"], change(scope, 1, "pause", "pause-readonly"), HUMAN)
    assert paused["job"]["state"] == "paused"


def test_history_pagination_scope_and_corruption(reconciliation_project):
    service, scope, payload = reconciliation_project
    authority = OporaReconciliation(service)
    first = authority.enroll(payload, HUMAN)
    bid = first["binding"]["id"]
    repo = authority.repository(**scope)
    page = repo.history(bid, limit=1)
    assert len(page["items"]) == 1 and page["nextCursor"] is not None
    assert repo.history(bid, int(page["nextCursor"]), limit=1)["items"][0]["kind"] == "control"
    with pytest.raises(ValueError):
        authority.history(scope["project"], "main", bid)
    with repo.db:
        repo.db.execute("UPDATE opora_reconciliation_records SET content=? WHERE id=?", ('{}', bid))
    with pytest.raises(ValueError):
        repo.read("binding", bid)


def test_historical_binding_survives_accepted_head_advance_and_merge(reconciliation_project):
    import time

    from backend.canvas.opora_reconciliation_finish import record_success
    from backend.canvas.opora_reconciliation_scope import historical_context
    from backend.canvas.reconciliation_test_support import data
    from database.repositories.opora_changesets import ChangesetRepository
    service, scope, payload = reconciliation_project
    authority = OporaReconciliation(service)
    enrolled = authority.enroll(payload, HUMAN)
    binding = enrolled["binding"]
    repo = authority.repository(**scope)
    jobs = ReconciliationJobs(repo.db, *repo.scope)
    now = time.time()
    with repo.db:
        repo.db.execute("BEGIN IMMEDIATE")
        claim = jobs.claim(now, "worker")
    # A valid new accepted record is stored while the remote read is in flight.
    accepted = ChangesetRepository(repo.db, *repo.scope)
    old = accepted.read(binding["acceptedRevision"])
    content = {k: v for k, v in old.items() if k != "id"}
    content.update(kind="acceptance", parentRevision=old["id"], proposalId="a" * 40, subject="Advanced plan")
    with repo.db:
        repo.db.execute("BEGIN IMMEDIATE")
        new = accepted.insert(content)
        accepted.advance(old["id"], new["id"])
    assert historical_context(service, *repo.scope, binding)["acceptedHead"] == new["id"]
    result = data(binding)
    result["repository"] = {k: binding["repository"][k] for k in ("id", "fullName")}
    result["pr"].update(baseRef=binding["repository"]["baseBranch"])
    with repo.db:
        repo.db.execute("BEGIN IMMEDIATE")
        assert record_success(repo, jobs, claim, binding, result, now + 1)
    row = authority.list(**scope, actor="human")["items"][0]
    assert row["revisionRelation"]["matchesCurrentAcceptedRevision"] is False
    assert row["lastSuccessfulObservation"]["data"]["pr"]["state"] == "merged"
    assert accepted.head() == new["id"]
    assert len(repo.records("event", binding["id"])) == 1
    # Pausing/resuming preserves the original plan pin even after head advance.
    authority.control(binding["id"], change(scope, 1, "pause", "pause-old"), HUMAN)
    resumed = authority.control(binding["id"], change(scope, 2, "resume", "resume-old"), HUMAN)
    assert resumed["binding"]["acceptedRevision"] == old["id"]


def test_archived_workspace_retains_readable_scoped_subscription_history(reconciliation_project):
    from backend.canvas.opora_reconciliation_scope import historical_context
    service, scope, payload = reconciliation_project
    authority = OporaReconciliation(service)
    first = authority.enroll(payload, HUMAN)
    binding = first["binding"]
    with service.registry_lock, service.db:
        service.db.execute("INSERT INTO archived_workspaces (id,project_id,reason,archived_at) VALUES(?,?,?,?)",
                           (scope["workspace"], scope["project"], "Archived by human", "2026-10-21T00:00:00Z"))
        service.db.execute("DELETE FROM workspaces WHERE id=?", (scope["workspace"],))
    current = authority.list(**scope, actor="human")
    assert not current["canConfigure"] and current["canPause"]
    assert current["items"][0]["binding"] == binding
    history = authority.history(scope["project"], scope["workspace"], binding["id"])
    assert len(history["items"]) == 2 and history["binding"] == binding
    with pytest.raises(ValueError):
        historical_context(service, scope["project"], scope["workspace"], binding)
    paused = authority.control(binding["id"], change(scope, 1, "pause", "pause-archive"), HUMAN)
    assert paused["job"]["state"] == "paused"


def test_request_receipt_cannot_expose_worker_owner_or_change_bound_generation(reconciliation_project):
    import json
    service, scope, payload = reconciliation_project
    authority = OporaReconciliation(service)
    first = authority.enroll(payload, HUMAN)
    repo = authority.repository(**scope)
    for mutation in ({"owner": "private-owner"}, {"generation": 999}):
        receipt = json.loads(json.dumps(first))
        receipt["job"].update(mutation)
        with repo.db:
            repo.db.execute("UPDATE opora_reconciliation_requests SET result=?", (json.dumps(receipt),))
        with pytest.raises(ValueError, match="receipt"):
            authority.enroll(payload, HUMAN)
