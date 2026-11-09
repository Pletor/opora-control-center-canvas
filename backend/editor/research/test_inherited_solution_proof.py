"""Ancestor input changes stale native milestone, card and search proof together."""
from copy import deepcopy
import pytest

from backend.brain_opora.determinism import milestones
from backend.brain_opora.determinism.test_milestones import service, SESSION, decide
from backend.brain_opora.determinism.test_milestone_evidence import result, submit
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.opora_agent_state_progress import attach
from backend.canvas.test_opora_changesets import baseline
from backend.canvas.test_opora_graph_proposals import accept, proposal
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.test_opora_executions import accept_graph_change
from backend.canvas.test_graph_card import node
from backend.editor.research.knowledge import solutions
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_executions import Executions
from database.repositories.intake_milestones import IntakeMilestones

SCOPE = {"project": "draft", "workspace": "draft"}


@pytest.mark.parametrize("draft_change", [None, "purpose", "goal", "node_rule", "scoped_rule"])
def test_inherited_inputs_have_one_selective_freshness_definition(service, draft_change):
    view = service.view("draft", "draft")
    graph = deepcopy(view["graph"])
    graph["nodes"].extend([{**node("parent"), "kind": "sector"}, {**node("sibling"), "kind": "sector"},
                            node("input_a"), node("input_b")])
    next(item for item in graph["nodes"] if item["id"] == "n1")["parentId"] = "parent"
    graph["edges"] = [{"id": key, "source": source, "target": target, "relation": "requires",
        "requirement": {"readiness": "design", "revision": 0}} for key, source, target in (
            ("parent_input", "parent", "input_a"), ("sibling_input", "sibling", "input_b"))]
    service.save_graph("draft", "draft", graph, view["digest"])
    steps = [{"id": role, "order": i, "title": role, "acceptance": [role], "dependsOn": [], "kind": "test",
              "files": ["tests/integration.py"]} for i, role in enumerate(("positive", "negative"), 1)]
    service.node_spec("draft", "draft", "n1", {**SCOPE, "node": "n1", "expected_revision": 0,
        "fields": {"goal": "Functional login", "non_goals": "", "acceptance": "Isolation", "steps": steps}})
    baseline(service)
    graphs = OporaGraphProposals(service)
    accept(graphs, proposal(graphs))
    authority = ExecutionResults(service)
    context = authority.context("draft", "draft", "n1")
    proof = {"nodeId": "n1", "acceptedRevision": context["acceptedHead"], **{
        role: {"stepId": role, "check": role, "command": f"pytest tests/integration.py -k {role}"} for role in ("positive", "negative")}}
    made = milestones.propose(service, SESSION, "a1", "Functional entry", [
        {"text": "Login and isolation", "cards": ["n1"], "verification": proof}], "t")
    decide(service, made["id"])
    execution = authority.claim({**SCOPE, "nodeId": "n1", "requestId": "integration", "ttlSeconds": 60,
        "expectedAcceptedHead": context["acceptedHead"], "expectedContextVersion": context["contextVersion"]}, "agent:integration")
    submit(authority, execution, result(proof))
    original = deepcopy(execution["assignment"])
    db = service.db_for("draft")

    def statuses():
        repo = ChangesetRepository(db, "draft", "draft")
        accepted = repo.read(repo.head())
        milestone = milestones.evaluate(db, "draft", IntakeMilestones(db).get(made["id"]))["verification"]["verified"]
        card = attach(db, "draft", "draft", [{"nodeId": "n1"}], accepted["documents"], repo.head())[0]["progressEvidence"]
        search = solutions(service, [SCOPE], "n1", 10, lambda *_: None)["solutions"][0]["verification"]
        return milestone, bool(card.get("verification", {}).get("verified")), bool(search.get("verified"))

    assert statuses() == (True, True, True)
    if draft_change:
        if draft_change == "purpose":
            current = service.view("draft", "draft")
            updated = deepcopy(current["graph"])
            next(item for item in updated["nodes"] if item["id"] == "parent")["purpose"] = "New inherited constraint"
            service.save_graph("draft", "draft", updated, current["digest"])
        elif draft_change == "goal":
            current = service.node_spec("draft", "draft", "parent")
            service.node_spec("draft", "draft", "parent", {**SCOPE, "node": "parent",
                "expected_revision": current["revision"], "fields": {**current["fields"], "goal": "New inherited goal"}})
        else:
            from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
            state = DesktopV3State(service)
            current = state.read("draft", "draft")
            value = deepcopy(current["state"])
            rule = {"id": "inherited", "text": "New inherited constraint", "kind": "must"}
            if draft_change == "scoped_rule":
                value["rules"].append({**rule, "scope": "node", "target": "parent"})
            else:
                value["nodes"].setdefault("parent", {"phase": "discover", "criteria": [], "steps": [], "actions": []})["rules"] = [rule]
            state.save({**SCOPE, "state": value, "expectedRevision": current["revision"]})
        assert statuses() == (True, True, False)
        assert Executions(db, "draft", "draft").read(execution["executionId"])["assignment"] == original
        return
    accept_graph_change(service, {"updateEdges": [{"id": "sibling_input", "source": "sibling", "target": "input_b", "port": "next",
        "requirement": {"readiness": "implemented", "revision": 0}}]})
    assert statuses() == (True, True, True)
    accept_graph_change(service, {"updateEdges": [{"id": "parent_input", "source": "parent", "target": "input_b", "port": "next",
        "requirement": {"readiness": "implemented", "revision": 0}}]})
    assert statuses() == (False, False, False)
    assert Executions(db, "draft", "draft").read(execution["executionId"])["assignment"] == original
