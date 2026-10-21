"""An agent can propose the first actual plan on an entirely empty Canvas."""
import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.test_graph_card import node
from backend.canvas.test_opora_changesets import AGENT, SCOPE, baseline
from backend.canvas.test_opora_graph_proposals import accept, proposal
from database.schema.opora_graph_schema import SCHEMA


@pytest.fixture
def empty_graphs(tmp_path):
    service = CanvasService(tmp_path / "data")
    service.view("draft", "draft")
    service.db_for("draft").executescript(SCHEMA)
    try:
        yield OporaGraphProposals(service)
    finally:
        service.close()


def test_empty_plan_propose_accept_then_execute(empty_graphs):
    graphs = empty_graphs
    item = proposal(graphs, plan={"nodes": [{"ref": "sector", "kind": "sector", "name": "Plan"},
                                            {"ref": "task", "kind": "node", "parent": "sector", "name": "Implement"}]})
    assert item["parentRevision"] is None and item["baseGraph"] == {"nodes": [], "edges": []}
    accepted = accept(graphs, item)
    assert accepted["kind"] == "graph-baseline" and accepted["parentRevision"] is None
    assert accepted["proposalId"] == item["id"] and accepted["graphManifestId"]
    authority = ExecutionResults(graphs.service)
    context = authority.context(**SCOPE, node=item["refs"]["task"])
    assert context["available"], context
    record = authority.claim({**SCOPE, "nodeId": item["refs"]["task"], "requestId": "first", "ttlSeconds": 60,
                              "expectedAcceptedHead": accepted["id"], "expectedContextVersion": context["contextVersion"]}, "agent:builder")
    assert record["acceptedRevision"] == accepted["id"] and record["assignment"]["acceptedRevision"] == accepted["id"]
    with pytest.raises(ValueError):
        baseline(graphs.service)


def test_other_initial_acceptance_requires_rebase(empty_graphs):
    first, sibling = proposal(empty_graphs, "One"), proposal(empty_graphs, "Two")
    accept(empty_graphs, first)
    with pytest.raises(ValueError, match="rebase"):
        accept(empty_graphs, sibling)
    context = empty_graphs.context(**SCOPE)
    moved = empty_graphs.rebase(sibling["id"], {**SCOPE, "expectedAcceptedHead": context["acceptedHead"],
                                               "expectedGraphDigest": context["graphDigest"]}, AGENT)
    assert moved["parentRevision"] == context["acceptedHead"] and moved["refs"] == sibling["refs"]
    assert accept(empty_graphs, moved)["kind"] == "graph-acceptance"


def test_spec_baseline_race_requires_graph_rebase(empty_graphs):
    service = empty_graphs.service
    view = service.view("draft", "draft")
    service.save_graph("draft", "draft", {"nodes": [node("existing")], "edges": []}, view["digest"])
    item = proposal(empty_graphs)
    baseline(service)
    with pytest.raises(ValueError, match="rebase"):
        accept(empty_graphs, item)
    context = empty_graphs.context(**SCOPE)
    moved = empty_graphs.rebase(item["id"], {**SCOPE, "expectedAcceptedHead": context["acceptedHead"],
                                            "expectedGraphDigest": context["graphDigest"]}, AGENT)
    assert moved["adoptionDocuments"] == [] and moved["requiresBaseAdoption"]
    accept(empty_graphs, moved)
