"""Public v1 adoption bridge and current-state safety share one accepted chain."""
import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.test_graph_card import node
from backend.canvas.test_opora_changesets import AGENT, SCOPE
from backend.canvas.test_opora_graph_addition_safety import closed
from backend.canvas.test_opora_graph_proposals import accept, graphs, proposal, service

__all__ = ["graphs", "service"]


def test_adoption_only_existing_graph_requires_ack_and_cannot_repeat(graphs):
    item = proposal(graphs, plan={"nodes": [], "edges": []})
    assert item["requiresBaseAdoption"] and item["additions"] == {"nodes": [], "edges": []}
    with pytest.raises(ValueError, match="Explicit adoption"):
        accept(graphs, item, adoptBaseGraphDigest=None)
    accept(graphs, item)
    with pytest.raises(ValueError):
        proposal(graphs, plan={"nodes": [], "edges": []})


def test_v1_edge_addition_rejects_already_closed_endpoint(graphs, service):
    closed(service, "a")
    with pytest.raises(ValueError, match="reopen"):
        proposal(graphs, plan={"edges": [{"from": "@a", "to": "@b"}]})


def test_v1_parent_closed_after_proposal_cannot_accept(graphs, service):
    item = proposal(graphs, plan={"nodes": [{"ref": "child", "kind": "node", "name": "Child", "parent": "@a"}]})
    closed(service, "a")
    with pytest.raises(ValueError, match="reopen"):
        accept(graphs, item)


def test_v1_edge_endpoint_closed_after_proposal_cannot_accept(graphs, service):
    item = proposal(graphs, plan={"edges": [{"from": "@a", "to": "@b"}]})
    closed(service, "b")
    with pytest.raises(ValueError, match="reopen"):
        accept(graphs, item)


def test_adoption_only_rebase_cannot_create_empty_first_graph_baseline(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    try:
        view = canvas.view("draft", "draft")
        canvas.save_graph("draft", "draft", {"nodes": [node("card")], "edges": []}, view["digest"])
        graphs = OporaGraphProposals(canvas)
        item = proposal(graphs, plan={"nodes": [], "edges": []})
        view = canvas.view("draft", "draft")
        canvas.save_graph("draft", "draft", {"nodes": [], "edges": []}, view["digest"], allow_removal=True)
        context = graphs.context(**SCOPE)
        with pytest.raises(ValueError, match="nonempty"):
            graphs.rebase(item["id"], {**SCOPE, "expectedAcceptedHead": None,
                                      "expectedGraphDigest": context["graphDigest"]}, AGENT)
        assert len(graphs.list(**SCOPE)["items"]) == 1
        assert graphs.context(**SCOPE)["acceptedHead"] is None
    finally:
        canvas.close()
