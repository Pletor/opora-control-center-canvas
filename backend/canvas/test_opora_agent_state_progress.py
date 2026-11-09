from backend.canvas.opora_agent_state_progress import attach
from backend.brain_opora.determinism.test_milestone_evidence import integration, result, submit
from backend.brain_opora.determinism.test_milestones import service
from database.repositories.opora_changesets import ChangesetRepository

__all__ = ["service", "integration"]


def test_projection_uses_accepted_design_and_pinned_functional_proof(service, integration):
    authority, record, _, proof = integration
    repo = ChangesetRepository(service.db_for("draft"), "draft", "draft")
    docs = repo.read(repo.head())["documents"]
    entries = [{"nodeId": "n1"}, {"nodeId": "n2"}, {"nodeId": "unrelated"}]
    before = attach(repo.db, "draft", "draft", entries, docs, repo.head())
    assert before[0]["progressEvidence"]["designAccepted"] is True
    assert "verification" not in before[0]["progressEvidence"]
    submit(authority, record, result(proof))
    after = attach(repo.db, "draft", "draft", entries, docs, repo.head())
    assert after[0]["progressEvidence"]["verification"]["verified"] is True
    assert after[1]["progressEvidence"]["verification"]["independent"] is False
    assert "verification" not in after[2]["progressEvidence"]
