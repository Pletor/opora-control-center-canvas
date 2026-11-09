"""Integration completion reuses real accepted specs, authenticated executions and receipts."""
import copy

import pytest

from backend.brain_opora.determinism import milestones
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.brain_opora.determinism.test_milestones import SESSION, close, decide, service
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.test_opora_changesets import baseline
from database.repositories.intake_milestones import IntakeMilestones
from database.repositories.intake_requirements import IntakeRequirements
from database.repositories.opora_executions import Executions

__all__ = ["service"]
SHA = "a" * 40


def prepare_integration(service):
    steps = [{"id": role, "order": i, "title": role, "acceptance": ["Login works" if i == 1 else "Other tenant denied"],
              "dependsOn": [], "kind": "test", "files": ["tests/integration.py"]}
             for i, role in enumerate(("positive", "negative"), 1)]
    service.node_spec("draft", "draft", "n1", {**SESSION_TO_SCOPE, "node": "n1", "expected_revision": 0,
        "fields": {"goal": "Functional login", "non_goals": "", "acceptance": "Login works; tenant isolation holds", "steps": steps}})
    head = baseline(service)["id"]
    from backend.canvas.opora_graph_proposals import OporaGraphProposals
    from backend.canvas.test_opora_graph_proposals import accept as accept_graph, proposal as graph_proposal
    graphs = OporaGraphProposals(service)
    head = accept_graph(graphs, graph_proposal(graphs, plan={"nodes": [], "edges": []}))["id"]
    proof = {"nodeId": "n1", "acceptedRevision": head,
             **{role: {"stepId": role, "check": role, "command": f"pytest tests/integration.py -k {role}"}
                for role in ("positive", "negative")}}
    made = milestones.propose(service, SESSION, "a1", "Functional entry", [
        {"text": "Login and isolation", "cards": ["n1", "n2", "n3"], "verification": proof}], "t")
    decide(service, made["id"])
    authority = ExecutionResults(service)
    context = authority.context("draft", "draft", "n1")
    record = authority.claim({**SESSION_TO_SCOPE, "nodeId": "n1", "requestId": "claim", "ttlSeconds": 60,
                             "expectedAcceptedHead": context["acceptedHead"], "expectedContextVersion": context["contextVersion"]},
                             "agent:integration")
    return authority, record, made, proof


SESSION_TO_SCOPE = {"project": "draft", "workspace": "draft"}


@pytest.fixture
def integration(service):
    return prepare_integration(service)


def result(proof):
    return {"summary": "Functional integration scenario including isolation",
            "selfChecks": {"headSha": SHA, "checks": [
                {"name": role, "command": proof[role]["command"], "status": "passed", "exitCode": 0,
                 "output": "1 passed"} for role in ("positive", "negative")]},
            "stepResults": [{"stepId": role, "status": "done", "evidence": {
                "notes": "Integration test", "checks": [role], "commits": [SHA]}}
                for role in ("positive", "negative")]}


def submit(authority, record, payload):
    return authority.submit(record["executionId"], {**SESSION_TO_SCOPE, "token": record["token"], "epoch": record["epoch"],
                                                   "requestId": "result", "result": payload})


def evaluate(service, made):
    db = service.db_for("draft")
    return milestones.evaluate(db, "draft", IntakeMilestones(db).get(made["id"]))


def test_complete_integration_requires_positive_negative_output_and_closure_then_wakes_once(service, integration):
    authority, record, made, proof = integration
    assert evaluate(service, made)["done"] is False
    receipt = submit(authority, record, result(proof))
    evidence = evaluate(service, made)
    assert evidence["verification"]["verified"] is True and evidence["done"] is False
    assert evidence["verification"]["receiptId"] == receipt["receiptId"]
    close(service, "n1", "n2", "n3")
    evidence = evaluate(service, made)
    assert evidence["done"] is True and evidence["closureProgress"] == 100
    assert evidence["verification"]["headSha"] == SHA
    assert evidence["verification"]["independent"] is False
    assert evidence["verification"]["level"] == "reported_evidence"
    db = service.db_for("draft")
    with db:
        IntakeRequirements(db).insert({"id": "rq_1", "workspaceId": "draft", "areaId": "a1", "title": "Next",
                                       "status": "deferred", "openCondition": made["id"], "createdAt": "t"})
        wake = milestones.wakes(db, "draft", None, "t")
        assert wake[0][1]["deferred"] == [{"id": "rq_1", "title": "Next"}]
        assert milestones.wakes(db, "draft", None, "t") == []


@pytest.mark.parametrize("break_case", ["negative_missing", "negative_red", "output_missing", "wrong_command", "wrong_commit", "prototype_only"])
def test_incomplete_or_unrelated_results_never_complete(service, integration, break_case):
    authority, record, made, proof = integration
    payload = result(proof)
    if break_case == "negative_missing": payload["stepResults"].pop()
    if break_case == "negative_red": payload["selfChecks"]["checks"][1].update(status="failed", exitCode=1)
    if break_case == "output_missing": payload["selfChecks"]["checks"][1].pop("output")
    if break_case == "wrong_command": payload["selfChecks"]["checks"][1]["command"] = "pytest unrelated.py"
    if break_case == "wrong_commit": payload["stepResults"][1]["evidence"]["commits"] = ["b" * 40]
    if break_case == "prototype_only": payload = {"summary": "Prototype accepted", "verified": True, "done": True}
    submit(authority, record, payload)
    close(service, "n1", "n2", "n3")
    evaluated = evaluate(service, made)
    assert evaluated["closureDone"] is True and evaluated["done"] is False
    assert evaluated["verification"]["verified"] is False


def test_mismatched_assignment_pin_and_later_attempt_invalidate_old_green(service, integration):
    authority, record, made, proof = integration
    submit(authority, record, result(proof))
    close(service, "n1", "n2", "n3")
    repo = Executions(service.db_for("draft"), "draft", "draft")
    changed = repo.read(record["executionId"])
    changed["assignmentDigest"] = "b" * 40
    with repo.db:
        repo.save(changed)
    assert evaluate(service, made)["done"] is False


def test_descriptor_must_name_distinct_accepted_tests_and_current_revision(service, integration):
    _, _, _, proof = integration
    for change in ({"acceptedRevision": "b" * 40}, {"negative": proof["positive"]},
                   {"positive": {**proof["positive"], "stepId": "missing"}}):
        broken = {**copy.deepcopy(proof), **change}
        with pytest.raises(GateError):
            milestones.propose(service, SESSION, "a1", "Invalid", [
                {"text": "Integration", "cards": ["n1"], "verification": broken}], "t")


def test_newer_unreported_attempt_does_not_reuse_old_green_receipt(service, integration):
    authority, record, made, proof = integration
    submit(authority, record, result(proof))
    context = authority.context("draft", "draft", "n1")
    newer = authority.claim({**SESSION_TO_SCOPE, "nodeId": "n1", "requestId": "newer", "ttlSeconds": 60,
        "expectedAcceptedHead": context["acceptedHead"], "expectedContextVersion": context["contextVersion"]}, "agent:integration")
    authority.release(newer["executionId"], {**SESSION_TO_SCOPE, "token": newer["token"], "epoch": newer["epoch"]})
    close(service, "n1", "n2", "n3")
    assert evaluate(service, made)["verification"]["reason"] == "integration_execution_not_reported"


def test_binding_selection_change_after_receipt_invalidates_functional_proof_and_required_input(service, integration):
    from backend.api.editor.test_research_routes import card
    from backend.editor.research import knowledge, service as research
    from backend.canvas.requirement_readiness import _verification
    authority, record, made, proof = integration
    submit(authority, record, result(proof))
    assert evaluate(service, made)["verification"]["verified"] is True
    research.apply(service, {"project": "draft", "workspace": "draft", "key": "source", "operations": [card("source")]}, "human")
    knowledge.bind(service, "draft", "draft", "n1", {"projectId": "draft", "workspaceId": "draft", "id": "source", "revision": 1},
                   0, False, lambda *args: None, "human")
    evaluated = evaluate(service, made)
    assert evaluated["verification"]["verified"] is False
    assert "binding selection changed" in evaluated["verification"]["detail"]
    with pytest.raises(ValueError, match="verification unresolved"):
        _verification(service, "draft", "draft", "n1", {"verification": {role: proof[role] for role in ("positive", "negative")}},
                      proof["acceptedRevision"], {"executionId": record["executionId"], "executionAcceptedRevision": proof["acceptedRevision"], "mergeSha": SHA})


def test_new_accepted_revision_and_wrong_workspace_invalidate_receipt(service, integration):
    from backend.canvas.test_opora_auto_rebase import propose
    from backend.canvas.test_opora_changesets import accept
    from backend.brain_opora.determinism import milestone_evidence
    authority, record, made, proof = integration
    submit(authority, record, result(proof))
    accepted = accept(service, propose(service, "n1", goal="Changed integration contract"), proof["acceptedRevision"])
    assert accepted["id"] != proof["acceptedRevision"]
    assert evaluate(service, made)["verification"]["verified"] is False
    assert milestone_evidence.evaluate(service.db_for("draft"), "draft", "main", [{"cards": ["n1"], "verification": proof}])["verified"] is False


def test_unrelated_accepted_edit_and_cosmetic_rename_preserve_original_proof(service, integration):
    from backend.canvas.test_opora_auto_rebase import propose
    from backend.canvas.test_opora_changesets import accept
    from backend.canvas.test_opora_executions import accept_graph_change
    authority, record, made, proof = integration
    submit(authority, record, result(proof))
    accept(service, propose(service, "a1", goal="Unrelated area's planning note"), proof["acceptedRevision"])
    accept_graph_change(service, {"updateNodes": [{"id": "n1", "fields": {"name": "Renamed login"}}]})
    evaluated = evaluate(service, made)["verification"]
    assert evaluated["verified"] is True
    assert evaluated["acceptedRevision"] == proof["acceptedRevision"]
    assert evaluated["currentAcceptedRevision"] != proof["acceptedRevision"]


def test_existing_heart_api_ingests_and_returns_pinned_integration_criteria(tmp_path, service):
    from fastapi.testclient import TestClient
    from backend.app.factory import create_app
    from backend.brain_opora.determinism import tokens
    from backend.canvas.test_canvas_plan import HEADERS, ORIGIN
    app = create_app(tmp_path / "api")
    with TestClient(app, base_url=ORIGIN) as client:
        canvas = app.state.service
        view = canvas.view("draft", "draft")
        canvas.save_graph("draft", "draft", service.view("draft", "draft")["graph"], view["digest"])
        authority, record, _, proof = prepare_integration(canvas)
        submit(authority, record, result(proof))
        close(canvas, "n1", "n2", "n3")
        client.post("/api/brain/gate-setting", headers=HEADERS, json={"project": "draft", "enabled": True})
        heart = {**HEADERS, tokens.HEADER: tokens.issue_heart(canvas, "draft", "draft")[1]}
        payload = {**SESSION_TO_SCOPE, "area": "a1", "title": "Verified login",
                   "criteria": [{"text": "Login and isolation", "cards": ["n1", "n2", "n3"], "verification": proof}]}
        created = client.post("/api/brain/heart/milestone", headers=heart, json=payload)
        assert created.status_code == 201, created.text
        assert created.json()["criteria"][0]["verification"] == proof
        activated = client.post("/api/intake/milestone", headers=HEADERS,
            json={**SESSION_TO_SCOPE, "milestoneId": created.json()["id"], "action": "activate"})
        assert activated.status_code == 200, activated.text
        milestone = client.get("/api/intake", params=SESSION_TO_SCOPE).json()["areas"][0]["milestone"]
        assert milestone["done"] is True and milestone["verification"]["independent"] is False
        assert milestone["verification"]["executionId"] == record["executionId"]
