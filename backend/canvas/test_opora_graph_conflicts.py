"""Explicit base adoption, divergent working context and immutable graph integrity."""
import copy
import json

import pytest

from backend.canvas.graph import digest
from backend.canvas.opora_graph_acceptance import OporaGraphAcceptance
from backend.canvas.test_graph_card import node
from backend.canvas.test_opora_changesets import AGENT, SCOPE, legacy_save
from backend.canvas.test_opora_graph_proposals import accept, proposal
from backend.canvas.test_opora_graph_proposals import graphs as graph_fixture
from backend.canvas.test_opora_graph_proposals import service as canvas_fixture

graphs, service = graph_fixture, canvas_fixture


def add_working(service, item):
    view = service.view("draft", "draft")
    graph = copy.deepcopy(view["graph"])
    graph["nodes"].append(item)
    service.save_graph("draft", "draft", graph, view["digest"])


def rebase(graphs, item):
    context = graphs.context(**SCOPE)
    return graphs.rebase(item["id"], {**SCOPE, "expectedAcceptedHead": context["acceptedHead"],
                                     "expectedGraphDigest": context["graphDigest"]}, AGENT)


def test_first_adoption_visibly_includes_missing_documents(graphs, service):
    add_working(service, node("working"))
    item = proposal(graphs)
    assert [doc["nodeId"] for doc in item["adoptionDocuments"]] == ["working"]
    result = accept(graphs, item)
    assert any(doc["nodeId"] == "working" for doc in result["documents"])


def test_changed_adoption_document_refuses_acceptance(graphs, service):
    add_working(service, node("working"))
    item = proposal(graphs)
    legacy_save(service, "working")
    with pytest.raises(ValueError, match="documents changed"):
        accept(graphs, item)
    moved = rebase(graphs, item)
    assert moved["refs"] == item["refs"] and moved["adoptionDocuments"] != item["adoptionDocuments"]
    accept(graphs, moved)


def test_existing_divergent_spec_cannot_be_silently_adopted(graphs, service):
    legacy_save(service)
    with pytest.raises(ValueError, match="specifications differ"):
        proposal(graphs)


def test_later_manifest_does_not_adopt_unrelated_working_cards(graphs, service):
    first = accept(graphs, proposal(graphs))
    add_working(service, node("unaccepted"))
    second = accept(graphs, proposal(graphs, "Next"))
    repo = graphs.repository(**SCOPE)
    manifest = repo.read(second["graphManifestId"], manifest=True)
    assert "unaccepted" not in {item["id"] for item in manifest["graph"]["nodes"]}
    assert "unaccepted" not in {item["nodeId"] for item in second["documents"]}
    assert first["graphManifestId"] != second["graphManifestId"]
    with pytest.raises(ValueError, match="anchor"):
        proposal(graphs, plan={"nodes": [{"ref": "x", "kind": "node", "name": "X", "parent": "@unaccepted"}]})


@pytest.mark.parametrize("conflict", ["name", "id"])
def test_rebase_rejects_changed_anchor_or_occupied_id(graphs, service, conflict):
    item = proposal(graphs, plan={"nodes": [{"ref": "x", "kind": "node", "name": "X", "parent": "@a"}]})
    view = service.view("draft", "draft")
    graph = copy.deepcopy(view["graph"])
    if conflict == "name":
        next(n for n in graph["nodes"] if n["id"] == "a")["name"] = "Changed anchor"
    else:
        graph["nodes"].append(node(item["refs"]["x"]))
    service.save_graph("draft", "draft", graph, view["digest"])
    with pytest.raises(ValueError, match="anchor|occupied"):
        rebase(graphs, item)


def test_corrupt_record_and_manifest_fail_closed(graphs, service):
    item = proposal(graphs)
    db = service.db_for("draft")
    with db:
        altered = {**item, "subject": "Tampered"}
        db.execute("UPDATE opora_graph_proposals SET content=? WHERE id=?", (json.dumps(altered), item["id"]))
    with pytest.raises(ValueError, match="integrity"):
        graphs.read(**SCOPE, record_id=item["id"])


def test_agent_cannot_accept_even_with_valid_proposal(graphs):
    item = proposal(graphs)
    with pytest.raises(ValueError):
        OporaGraphAcceptance(graphs.service).accept(item["id"], {**SCOPE, "expectedAcceptedHead": item["parentRevision"],
            "expectedGraphDigest": item["graphDigest"], "adoptBaseGraphDigest": item["graphDigest"]}, AGENT)


def test_first_proposal_rebase_preserves_existing_positions(graphs, service):
    item = proposal(graphs)
    add_working(service, node("sibling", x=300, y=400))
    before = copy.deepcopy(service.view("draft", "draft")["graph"])
    rebased = rebase(graphs, item)
    assert digest(rebased["baseGraph"]) == digest(before)
    assert rebased["refs"] == item["refs"]
    assert service.view("draft", "draft")["graph"] == before
