"""Accepted design, merged implementation and verification are separate gates."""
from copy import deepcopy

import pytest

from backend.canvas.opora_execution_validation import assignment
from backend.canvas.opora_execution_context import collect
from backend.canvas.requirement_readiness import require_inputs
from backend.canvas.test_opora_graph_changes import approve, change, edits, service
from backend.canvas.test_opora_graph_proposals import graphs
from database.repositories.opora_executions import Executions


def sparse_assignment(service):
    from backend.canvas.opora_execution_context import prepare
    from backend.canvas.opora_executions import OporaExecutions
    prepare(OporaExecutions(service), {"project": "draft", "workspace": "draft", "nodeId": "a", "contextProtocolVersion": 2})
    db = service.db_for("draft")
    with db:
        db.execute("BEGIN IMMEDIATE")
        return collect(service, db, "draft", "draft", "a")


def dependency(edits, readiness=None, verification=None, port="action"):
    from database.repositories.opora_context_bindings import enroll
    with edits.service.db:
        edits.service.db.execute("BEGIN IMMEDIATE")
        enroll(edits.service.db, "draft", "draft")
    context = edits.specifications.context("draft", "draft")
    revision = next(doc["revision"] for doc in context["acceptedDocuments"] if doc["nodeId"] == "b")
    edge = {"from": "@a", "to": "@b", "port": port, "relation": "requires"}
    if readiness:
        edge["requirement"] = {"readiness": readiness, "revision": revision}
        if verification:
            edge["requirement"]["verification"] = verification
    item = change(edits, {"draftVersion": 3, "edges": [edge]})
    approve(edits, item)
    return revision


def test_accepted_design_is_pinned_in_v1_and_v2_assignments(edits, service):
    revision = dependency(edits, "design")
    value = assignment(service, "draft", "draft", "a")
    assert value["requiredInputs"][0]["revision"] == revision
    assert value["requiredInputs"][0]["readiness"] == "design"
    sparse, _ = sparse_assignment(service)
    assert sparse["requiredInputs"] == value["requiredInputs"]
    saved = deepcopy(value)
    view = service.view("draft", "draft")
    graph = deepcopy(view["graph"])
    next(edge for edge in graph["edges"] if edge.get("relation") == "requires")["requirement"]["revision"] += 1
    service.save_graph("draft", "draft", graph, view["digest"])
    assert value == saved
    with pytest.raises(ValueError, match="accepted graph"):
        assignment(service, "draft", "draft", "a")


@pytest.mark.parametrize("readiness, message", [(None, "unresolved"), ("implemented", "merged implementation"), ("verified", "merged implementation")])
def test_design_or_unspecified_input_cannot_prove_implementation(edits, service, readiness, message):
    dependency(edits, readiness)
    with pytest.raises(ValueError, match=message):
        assignment(service, "draft", "draft", "a")
    with pytest.raises(ValueError, match=message):
        sparse_assignment(service)


def test_stale_target_revision_is_rejected_even_if_historical_revision_exists(edits, service):
    revision = dependency(edits, "design")
    context = edits.specifications.context("draft", "draft")
    docs = deepcopy(context["acceptedDocuments"])
    next(doc for doc in docs if doc["nodeId"] == "b")["revision"] = revision + 1
    with pytest.raises(ValueError, match="stale"):
        require_inputs(service, "draft", "draft", "a", context["acceptedHead"], service.view("draft", "draft")["graph"], docs)


def test_implemented_input_requires_merge_bound_to_exact_document(edits, service, monkeypatch):
    from backend.canvas import opora_agent_state_pulls as pulls

    dependency(edits, "implemented")
    context = edits.specifications.context("draft", "draft")
    doc = next(doc for doc in context["acceptedDocuments"] if doc["nodeId"] == "b")
    monkeypatch.setattr(pulls, "read", lambda *_: [{"executionId": "execution", "cardId": "b", "state": "merged", "mergeSha": "a" * 40}])
    monkeypatch.setattr(Executions, "read", lambda *_: {"acceptedRevision": context["acceptedHead"], "assignment": {"documents": [doc]}})
    monkeypatch.setattr(Executions, "history", lambda *_: [{"executionId": "execution", "acceptedRevision": context["acceptedHead"], "assignment": {"documents": [doc]}}])
    result = assignment(service, "draft", "draft", "a")
    assert result["requiredInputs"][0]["executionId"] == "execution"
    assert result["requiredInputs"][0]["mergeSha"] == "a" * 40
    cosmetic = change(edits, {"updateNodes": [
        {"id": "a", "fields": {"name": "Consumer renamed"}},
        {"id": "b", "fields": {"name": "Input renamed"}},
    ]})
    approve(edits, cosmetic)
    assert assignment(service, "draft", "draft", "a")["requiredInputs"][0]["executionId"] == "execution"
    contract_change = change(edits, {"edges": [{"from": "@b", "to": "@app", "port": "rule", "relation": "requires",
        "requirement": {"readiness": "design", "revision": 0}}]})
    approve(edits, contract_change)
    with pytest.raises(ValueError, match="exact accepted revision"):
        assignment(service, "draft", "draft", "a")
    wrong = {**doc, "revision": doc["revision"] + 1}
    monkeypatch.setattr(Executions, "read", lambda *_: {"acceptedRevision": context["acceptedHead"], "assignment": {"documents": [wrong]}})
    monkeypatch.setattr(Executions, "history", lambda *_: [{"executionId": "execution", "acceptedRevision": context["acceptedHead"], "assignment": {"documents": [wrong]}}])
    with pytest.raises(ValueError, match="exact accepted revision"):
        assignment(service, "draft", "draft", "a")


def test_claim_is_blocked_before_any_lease_or_execution_write(edits, service):
    from backend.canvas.opora_executions import OporaExecutions

    dependency(edits)
    db = service.db_for("draft")
    before = [db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("card_leases", "opora_executions")]
    authority = OporaExecutions(service)
    with pytest.raises(ValueError, match="unresolved"):
        authority.claim({"project": "draft", "workspace": "draft", "nodeId": "a", "expectedAcceptedHead": None,
                         "expectedContextVersion": None, "requestId": "blocked-input", "ttlSeconds": 60}, "agent:test")
    assert [db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("card_leases", "opora_executions")] == before


def test_verified_input_uses_real_pinned_positive_negative_receipt(service, monkeypatch):
    from backend.canvas.opora_graph_changes import OporaGraphChanges
    from backend.canvas.opora_graph_proposals import OporaGraphProposals
    from backend.canvas.opora_execution_results import ExecutionResults
    from backend.canvas.test_opora_changesets import baseline
    from backend.canvas.test_opora_graph_proposals import accept, proposal
    from backend.brain_opora.determinism.test_milestone_evidence import result
    from backend.canvas import opora_agent_state_pulls as pulls

    scope = {"project": "draft", "workspace": "draft"}
    steps = [{"id": role, "order": i, "title": role, "acceptance": [role], "dependsOn": [],
              "kind": "test", "files": ["tests/integration.py"]} for i, role in enumerate(("positive", "negative"), 1)]
    service.node_spec("draft", "draft", "b", {**scope, "node": "b", "expected_revision": 0,
        "fields": {"goal": "Functional entry", "non_goals": "", "acceptance": "Tenant isolation", "steps": steps}})
    baseline(service)
    proposals = OporaGraphProposals(service)
    accept(proposals, proposal(proposals))
    edits = OporaGraphChanges(service)
    cases = {role: {"stepId": role, "check": role, "command": f"pytest tests/integration.py -k {role}"}
             for role in ("positive", "negative")}
    dependency(edits, "verified", cases)
    authority = ExecutionResults(service)
    context = authority.context("draft", "draft", "b")
    execution = authority.claim({**scope, "nodeId": "b", "requestId": "verify-input", "ttlSeconds": 60,
        "expectedAcceptedHead": context["acceptedHead"], "expectedContextVersion": context["contextVersion"]}, "agent:input")
    monkeypatch.setattr(pulls, "read", lambda *_: [{"executionId": execution["executionId"], "cardId": "b", "state": "merged", "mergeSha": "a" * 40}])
    with pytest.raises(ValueError, match="verification unresolved"):
        assignment(service, "draft", "draft", "a")

    receipt = authority.submit(execution["executionId"], {**scope, "token": execution["token"], "epoch": execution["epoch"],
        "requestId": "result", "result": result(cases)})
    captured = assignment(service, "draft", "draft", "a")
    evidence = captured["requiredInputs"][0]["verification"]
    assert evidence["verified"] and evidence["receiptId"] == receipt["receiptId"]
    assert evidence["independent"] is False
    assert evidence["headSha"] == "a" * 40
    # A receipt remains historical, but it must stop proving today's changed scene.
    from backend.editor.storyboard.storyboard import StoryboardService
    from backend.editor.storyboard.test_storyboard import board
    from backend.brain_opora.determinism.milestone_evidence import evaluate
    original = deepcopy(Executions(service.db_for("draft"), "draft", "draft").read(execution["executionId"])["assignment"])
    StoryboardService(service).save({**scope, "nodeId": "b", "expected_revision": 0, "storyboard": board(title="New login behavior")})
    proof = evaluate(service.db_for("draft"), "draft", "draft", [{"cards": ["b"], "verification": {
        "nodeId": "b", "acceptedRevision": execution["acceptedRevision"], **cases}}])
    assert proof["verified"] is False and "Storyboard input changed" in proof["detail"]
    with pytest.raises(ValueError, match="accepted manifest"):
        assignment(service, "draft", "draft", "a")
    assert Executions(service.db_for("draft"), "draft", "draft").read(execution["executionId"])["assignment"] == original


@pytest.mark.parametrize("readiness", ["implemented", "verified"])
def test_newest_merged_execution_wins_over_lexical_link_order(edits, service, monkeypatch, readiness):
    from backend.canvas import opora_agent_state_pulls as pulls
    from backend.brain_opora.determinism import milestone_evidence
    cases = {role: {"stepId": role, "check": role, "command": f"pytest -k {role}"} for role in ("positive", "negative")}
    dependency(edits, readiness, cases if readiness == "verified" else None)
    context = edits.specifications.context("draft", "draft")
    doc = next(doc for doc in context["acceptedDocuments"] if doc["nodeId"] == "b")
    monkeypatch.setattr(pulls, "read", lambda *_: [
        {"executionId": identifier, "cardId": "b", "state": "merged", "mergeSha": sha * 40}
        for identifier, sha in (("aaa_old", "a"), ("zzz_new", "b"))])
    monkeypatch.setattr(Executions, "history", lambda *_: [
        {"executionId": identifier, "acceptedRevision": context["acceptedHead"], "assignment": {"documents": [doc]}}
        for identifier in ("zzz_new", "aaa_old")])
    monkeypatch.setattr(milestone_evidence, "evaluate", lambda *_: {"verified": True, "executionId": "zzz_new", "headSha": "b" * 40})
    assert assignment(service, "draft", "draft", "a")["requiredInputs"][0]["executionId"] == "zzz_new"


def test_next_port_requirement_does_not_deadlock_required_target_claim(edits, service):
    from backend.canvas.opora_executions import OporaExecutions
    dependency(edits, "design", port="next")
    authority = OporaExecutions(service)
    context = authority.context("draft", "draft", "b")
    execution = authority.claim({"project": "draft", "workspace": "draft", "nodeId": "b", "requestId": "input-first",
        "ttlSeconds": 60, "expectedAcceptedHead": context["acceptedHead"], "expectedContextVersion": context["contextVersion"]}, "agent:target")
    assert execution["nodeId"] == "b"


@pytest.mark.parametrize("protocol", [1, 2])
def test_ancestor_required_input_gates_child_and_excludes_sibling_constraints(service, monkeypatch, protocol):
    from backend.canvas.opora_graph_changes import OporaGraphChanges
    from backend.canvas.opora_graph_proposals import OporaGraphProposals
    from backend.canvas.test_opora_changesets import baseline
    from backend.canvas.test_opora_graph_proposals import accept, proposal
    from backend.canvas.test_graph_card import node
    from backend.canvas import opora_agent_state_pulls as pulls
    view = service.view("draft", "draft")
    graph = deepcopy(view["graph"])
    graph["nodes"].extend([{**node("scope"), "kind": "sector"}, {**node("sibling"), "kind": "sector"}])
    next(item for item in graph["nodes"] if item["id"] == "a")["parentId"] = "scope"
    service.save_graph("draft", "draft", graph, view["digest"])
    baseline(service)
    proposals = OporaGraphProposals(service)
    accept(proposals, proposal(proposals))
    edits = OporaGraphChanges(service)
    item = change(edits, {"edges": [
        {"from": "@scope", "to": "@b", "relation": "requires", "requirement": {"readiness": "implemented", "revision": 0}},
        {"from": "@sibling", "to": "@app", "relation": "requires"},
    ]})
    approve(edits, item)
    capture = lambda: assignment(service, "draft", "draft", "a") if protocol == 1 else sparse_assignment(service)[0]
    with pytest.raises(ValueError, match="merged implementation"):
        capture()
    context = edits.specifications.context("draft", "draft")
    doc = next(doc for doc in context["acceptedDocuments"] if doc["nodeId"] == "b")
    monkeypatch.setattr(pulls, "read", lambda *_: [{"executionId": "input", "cardId": "b", "state": "merged", "mergeSha": "a" * 40}])
    monkeypatch.setattr(Executions, "history", lambda *_: [{"executionId": "input", "acceptedRevision": context["acceptedHead"], "assignment": {"documents": [doc]}}])
    captured = capture()
    assert len(captured["requiredInputs"]) == 1
    assert captured["requiredInputs"][0]["sourceNodeId"] == "scope"
    assert captured["requiredInputs"][0]["nodeId"] == "b"
    assert any(document["nodeId"] == "b" for document in captured["documents"])
    saved = deepcopy(captured)
    view = service.view("draft", "draft")
    graph = deepcopy(view["graph"])
    next(edge for edge in graph["edges"] if edge["source"] == "scope")["requirement"]["revision"] = 1
    service.save_graph("draft", "draft", graph, view["digest"])
    assert captured == saved
    with pytest.raises(ValueError):
        capture()
