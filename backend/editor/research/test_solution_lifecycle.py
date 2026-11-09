"""Accepted historical solution proofs survive ordinary milestone progression, not rejection."""
from backend.brain_opora.determinism import milestones
from backend.brain_opora.determinism.test_milestone_evidence import integration, result, submit
from backend.brain_opora.determinism.test_milestones import SESSION, decide, service
from backend.editor.research.test_solution_verification import solutions
from database.repositories.intake_milestones import IntakeMilestones

__all__ = ["service", "integration"]


def replacement(service, title):
    made = milestones.propose(service, SESSION, "a1", title, [{"text": "Next work", "cards": ["n3"]}], title)
    decide(service, made["id"])
    return made


def test_native_verified_solution_survives_two_replacements_with_exact_original_pins(service, integration):
    authority, record, original, proof = integration
    receipt = submit(authority, record, result(proof))
    second = replacement(service, "Second")
    replacement(service, "Third")
    repository = IntakeMilestones(service.db_for("draft"))
    assert repository.get(original["id"])["replacedBy"] == second["id"]
    [solution] = solutions(service)
    assert solution["verification"]["status"] == "reported_evidence"
    assert solution["verification"]["executionId"] == record["executionId"]
    assert solution["verification"]["receiptId"] == receipt["receiptId"]
    assert solution["verification"]["acceptedRevision"] == proof["acceptedRevision"]
    assert solution["verification"]["milestoneId"] == original["id"]
    assert solution["verification"]["milestoneAcceptance"] == "replaced"


def test_explicit_active_rejection_rejected_proposal_and_unknown_legacy_never_prove_solution(service, integration):
    authority, record, original, proof = integration
    submit(authority, record, result(proof))
    decide(service, original["id"], "reject")
    assert solutions(service)[0]["verification"]["status"] == "unknown"
    proposed = milestones.propose(service, SESSION, "a1", "Rejected proposal", [
        {"text": "Same tests", "cards": ["n1"], "verification": proof}], "t2")
    decide(service, proposed["id"], "reject")
    repository = IntakeMilestones(service.db_for("draft"))
    with repository.db:
        repository.insert({"id": "legacy", "workspaceId": "draft", "areaId": "a1", "title": "Unknown legacy",
            "criteria": proposed["criteria"], "status": "superseded", "createdAt": "t0", "replacedBy": original["id"]})
    assert repository.proof_candidates("draft") == []
    assert solutions(service)[0]["verification"]["status"] == "unknown"


def test_relevant_contract_change_invalidates_historical_proof_after_replacement(service, integration):
    from backend.canvas.test_opora_auto_rebase import propose
    from backend.canvas.test_opora_changesets import accept
    authority, record, _, proof = integration
    submit(authority, record, result(proof))
    replacement(service, "Next milestone")
    assert solutions(service)[0]["verification"]["status"] == "reported_evidence"
    accept(service, propose(service, "n1", goal="New identity contract"), proof["acceptedRevision"])
    assert solutions(service)[0]["verification"]["status"] in ("unknown", "unproven")
