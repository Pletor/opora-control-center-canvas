"""Shared accepted chain preserves manifests and controls fresh execution eligibility."""
import copy

import pytest

from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.test_opora_changesets import SCOPE
from backend.canvas.test_opora_changesets import accept as accept_spec
from backend.canvas.test_opora_changesets import propose as propose_spec
from backend.canvas.test_opora_graph_initial import empty_graphs as initial_fixture
from backend.canvas.test_opora_graph_proposals import accept, proposal

empty_graphs = initial_fixture


def test_graph_spec_graph_chain_carries_manifest_exactly(empty_graphs):
    graphs = empty_graphs
    first = proposal(graphs)
    root = accept(graphs, first)
    specifications = propose_spec(graphs.service, nodes=(first["refs"]["new"],))
    edited = accept_spec(graphs.service, specifications, root["id"])
    assert edited["graphManifestId"] == root["graphManifestId"]
    final = accept(graphs, proposal(graphs, "Second card"))
    assert final["parentRevision"] == edited["id"] and final["graphManifestId"] != root["graphManifestId"]
    assert {item["nodeId"] for item in final["documents"]} > {first["refs"]["new"]}
    assert graphs.specifications.revision("draft", "draft", root["id"]) == root


@pytest.mark.parametrize("change", ["purpose", "edge", "layout"])
def test_new_claim_checks_accepted_graph_before_capture(empty_graphs, change):
    item = proposal(empty_graphs, plan={"nodes": [{"ref": "one", "kind": "node", "name": "One"},
                                                {"ref": "two", "kind": "node", "name": "Two"}]})
    accept(empty_graphs, item)
    service = empty_graphs.service
    view = service.view("draft", "draft")
    graph = copy.deepcopy(view["graph"])
    if change == "edge":
        graph["edges"].append({"id": "working-edge", "source": item["refs"]["one"], "target": item["refs"]["two"]})
    elif change == "purpose":
        graph["nodes"][0]["purpose"] = "Unapproved"
    else:
        graph["nodes"][0]["x"] += 10
    service.save_graph("draft", "draft", graph, view["digest"])
    context = ExecutionResults(service).context(**SCOPE, node=item["refs"]["one"])
    assert context["available"] == (change == "layout"), context
    if change != "layout":
        assert "accepted graph" in context["unavailableReason"]


def test_specs_only_revision_keeps_rejecting_unapproved_working_graph(empty_graphs):
    first = proposal(empty_graphs)
    root = accept(empty_graphs, first)
    service = empty_graphs.service
    view = service.view("draft", "draft")
    graph = copy.deepcopy(view["graph"])
    graph["nodes"][0]["purpose"] = "Working structural edit"
    service.save_graph("draft", "draft", graph, view["digest"])
    edited = accept_spec(service, propose_spec(service, nodes=(first["refs"]["new"],)), root["id"])
    assert edited["graphManifestId"] == root["graphManifestId"]
    assert not ExecutionResults(service).context(**SCOPE, node=first["refs"]["new"])["available"]
    assert OporaGraphProposals(service).context(**SCOPE)["graphManifestId"] == root["graphManifestId"]
