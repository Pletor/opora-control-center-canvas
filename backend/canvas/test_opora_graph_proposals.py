"""Graph additions remain immutable until one atomic human acceptance."""
import copy

import pytest

from backend.canvas.opora_graph_acceptance import OporaGraphAcceptance
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.test_opora_changesets import AGENT, HUMAN, SCOPE, baseline
from backend.canvas.test_opora_changesets import service as canvas_fixture
from database.repositories.opora_changesets import ChangesetRepository
from database.schema.opora_graph_schema import SCHEMA

service = canvas_fixture


@pytest.fixture
def graphs(service):
    service.db_for("draft").executescript(SCHEMA)
    baseline(service)
    return OporaGraphProposals(service)


def proposal(graphs, name="New card", plan=None):
    context = graphs.context(**SCOPE)
    return graphs.create({**SCOPE, "parentRevision": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
                          "subject": name, "plan": plan or {"nodes": [{"ref": "new", "kind": "node", "name": name}]}}, AGENT)


def accept(graphs, item, **overrides):
    context = graphs.context(**SCOPE)
    return OporaGraphAcceptance(graphs.service).accept(item["id"], {**SCOPE,
        "expectedAcceptedHead": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
        "adoptBaseGraphDigest": item["graphDigest"] if item["requiresBaseAdoption"] else None, **overrides}, HUMAN)


def test_proposal_is_immutable_acceptance_has_manifest_and_default_documents(graphs, service):
    before = copy.deepcopy(service.view("draft", "draft"))
    item = proposal(graphs)
    node_id = item["refs"]["new"]
    assert service.view("draft", "draft")["graph"] == before["graph"]
    assert item["requiresBaseAdoption"] and not item["accepted"]
    with pytest.raises(ValueError, match="Explicit adoption"):
        accept(graphs, item, adoptBaseGraphDigest=None)
    result = accept(graphs, item)
    assert any(node["id"] == node_id for node in service.view("draft", "draft")["graph"]["nodes"])
    document = next(doc for doc in result["documents"] if doc["nodeId"] == node_id)
    assert document["revision"] == 1 and document["fields"] == {"goal": "", "non_goals": "", "acceptance": ""}
    assert result["graphManifestId"] and graphs.read(**SCOPE, record_id=item["id"])["accepted"]
    later = accept(graphs, proposal(graphs, "Later"))
    assert accept(graphs, item)["id"] == result["id"]
    assert graphs.context(**SCOPE)["acceptedHead"] == later["id"]


def test_sibling_rebase_preserves_ids_and_creates_new_object(graphs, service):
    left, right = proposal(graphs, "Left"), proposal(graphs, "Right")
    accept(graphs, left)
    with pytest.raises(ValueError, match="rebase"):
        accept(graphs, right)
    context = graphs.context(**SCOPE)
    moved = graphs.rebase(right["id"], {**SCOPE, "expectedAcceptedHead": context["acceptedHead"],
                                      "expectedGraphDigest": context["graphDigest"]}, AGENT)
    assert moved["id"] != right["id"] and moved["refs"] == right["refs"]
    assert moved["supersedes"] == right["id"] and not moved["requiresBaseAdoption"]
    accept(graphs, moved)
    ids = {node["id"] for node in service.view("draft", "draft")["graph"]["nodes"]}
    assert {left["refs"]["new"], right["refs"]["new"]} <= ids


def test_failure_after_graph_and_documents_rolls_back_everything(graphs, service, monkeypatch):
    item = proposal(graphs)
    before, head = copy.deepcopy(service.view("draft", "draft")["graph"]), graphs.context(**SCOPE)["acceptedHead"]
    def fail(*args):
        raise RuntimeError("injected ref failure")
    monkeypatch.setattr(ChangesetRepository, "advance", fail)
    with pytest.raises(RuntimeError, match="injected"):
        accept(graphs, item)
    assert service.view("draft", "draft")["graph"] == before
    assert graphs.context(**SCOPE)["acceptedHead"] == head
    db = service.db_for("draft")
    assert db.execute("SELECT COUNT(*) FROM opora_graph_manifests").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM node_spec_revisions WHERE node_id=?", (item["refs"]["new"],)).fetchone()[0] == 0


@pytest.mark.parametrize("field", ["site", "gateNodeId", "rules", "blocks", "text", "criteria", "agentRole"])
def test_forbidden_addition_fields_are_rejected_before_build(graphs, field):
    with pytest.raises(ValueError, match="Unsupported"):
        proposal(graphs, plan={"nodes": [{"ref": "x", "kind": "node", "name": "X", field: "value"}]})


def test_list_is_sparse_and_detail_scope_checked(graphs):
    item = proposal(graphs)
    summary = graphs.list(**SCOPE)["items"][0]
    assert summary["nodeCount"] == 1 and "baseGraph" not in summary and "specifications" not in summary
    with pytest.raises(ValueError):
        graphs.read("draft", "elsewhere", item["id"])
