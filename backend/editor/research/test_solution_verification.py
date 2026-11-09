"""Federated solution status comes from real scoped executions, never research badges."""
from copy import deepcopy

import pytest

from backend.brain_opora.determinism.test_milestone_evidence import integration, result, submit
from backend.brain_opora.determinism.test_milestones import service
from backend.editor.research import knowledge, service as research
from backend.api.editor.test_research_routes import card

__all__ = ["service", "integration"]
SCOPE = {"project": "draft", "workspace": "draft"}


def solutions(service):
    return knowledge.solutions(service, [SCOPE], "n1", 10, lambda *_: None)["solutions"]


def test_actual_native_receipt_surfaces_exact_reported_evidence_pins(service, integration):
    authority, record, _, proof = integration
    assert solutions(service)[0]["verification"]["status"] == "unknown"
    receipt = submit(authority, record, result(proof))
    [solution] = solutions(service)
    verification = solution["verification"]
    assert verification["status"] == "reported_evidence"
    assert verification["verified"] is True and verification["independent"] is False
    assert verification["level"] == "reported_evidence"
    assert verification["executionId"] == record["executionId"]
    assert verification["receiptId"] == receipt["receiptId"]
    assert verification["acceptedRevision"] == record["acceptedRevision"]
    assert verification["assignmentDigest"] == record["assignmentDigest"]
    assert verification["headSha"] == "a" * 40
    assert verification["graphDigest"] == solution["snapshot"]["graphDigest"]
    assert solution["snapshots"][0]["verification"] == verification


def test_verified_research_badge_does_not_become_functional_solution_proof(service, integration):
    finding = card("fact", verification={"status": "verified", "method": "Read documentation", "at": "2026-11-09"},
                   sources=[{"ref": "https://example.org/spec", "platform": "web", "quote": "Session contract", "title": "Specification", "accessedAt": "2026-11-09"}])
    finding["refs"]["nodeIds"] = ["n1"]
    research.apply(service, {**SCOPE, "key": "verified-research", "operations": [finding]}, "human")
    [solution] = solutions(service)
    assert solution["evidence"][0]["verification"]["status"] == "verified"
    assert solution["verification"]["status"] == "unknown"


def test_changed_selected_binding_or_accepted_contract_removes_solution_proof(service, integration):
    from backend.canvas.test_opora_auto_rebase import propose
    from backend.canvas.test_opora_changesets import accept
    authority, record, _, proof = integration
    submit(authority, record, result(proof))
    assert solutions(service)[0]["verification"]["status"] == "reported_evidence"
    research.apply(service, {**SCOPE, "key": "new-source", "operations": [card("source")]}, "human")
    knowledge.bind(service, "draft", "draft", "n1", {"projectId": "draft", "workspaceId": "draft", "id": "source", "revision": 1},
                   0, False, lambda *_: None, "human")
    assert solutions(service)[0]["verification"]["status"] in ("unknown", "unproven")
    accept(service, propose(service, "n1", goal="New login contract"), proof["acceptedRevision"])
    assert solutions(service)[0]["verification"]["status"] in ("unknown", "unproven")


def test_unaccepted_displayed_solution_cannot_inherit_old_accepted_proof(service, integration):
    authority, record, _, proof = integration
    submit(authority, record, result(proof))
    view = service.view("draft", "draft")
    graph = deepcopy(view["graph"])
    next(node for node in graph["nodes"] if node["id"] == "n1")["purpose"] = "Different working solution"
    service.save_graph("draft", "draft", graph, view["digest"])
    assert solutions(service)[0]["verification"]["status"] == "unproven"


def test_denied_scope_is_rejected_before_reading_any_solution_proof(service, monkeypatch):
    from backend.editor.research import solution_verification
    from backend.brain_opora.determinism.gate_payloads import GateError
    monkeypatch.setattr(solution_verification, "project", lambda *_: pytest.fail("Unauthorized proof read"))
    def authorize(project, *_):
        if project == "foreign":
            raise GateError(403, "gate_scope", "Forbidden", "")
    with pytest.raises(GateError):
        knowledge.solutions(service, [SCOPE, {"project": "foreign", "workspace": "draft"}], "n1", 10, authorize)


def test_solution_api_pilot_returns_native_functional_proof_and_exact_origin(tmp_path, service):
    from fastapi.testclient import TestClient
    from backend.app.factory import create_app
    from backend.canvas.test_canvas_plan import HEADERS, ORIGIN
    from backend.brain_opora.determinism.test_milestone_evidence import prepare_integration
    with TestClient(create_app(tmp_path / "api"), base_url=ORIGIN) as client:
        canvas = client.app.state.service
        canvas.save_graph("draft", "draft", service.view("draft", "draft")["graph"], canvas.view("draft", "draft")["digest"])
        authority, record, _, proof = prepare_integration(canvas)
        submit(authority, record, result(proof))
        response = client.post("/api/research/knowledge-search", headers=HEADERS, json={**SCOPE,
            "scopes": [SCOPE], "query": "n1", "resultType": "solution"})
        assert response.status_code == 200, response.text
        [solution] = response.json()["solutions"]
        assert solution["solutionRef"] == {"projectId": "draft", "nodeId": "n1"}
        assert solution["snapshot"]["workspaceId"] == "draft"
        assert solution["verification"]["status"] == "reported_evidence"
        assert solution["verification"]["executionId"] == record["executionId"]
        assert solution["verification"]["independent"] is False
