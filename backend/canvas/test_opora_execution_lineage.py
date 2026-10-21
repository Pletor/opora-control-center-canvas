"""Accepted execution lineage checks use immutable graph and specification records."""
import copy

import pytest

from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.opora_execution_lineage import validate_accepted_lineage
from backend.canvas.opora_graph_change_acceptance import OporaGraphChangeAcceptance
from backend.canvas.opora_graph_changes import OporaGraphChanges
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.opora_hub_store import canonical
from backend.canvas.test_graph_card import node
from backend.canvas.test_opora_changesets import AGENT, HUMAN, SCOPE, baseline
from backend.canvas.test_opora_changesets import accept as accept_spec
from backend.canvas.test_opora_changesets import propose as propose_spec
from backend.canvas.test_opora_graph_initial import empty_graphs as initial_fixture
from backend.canvas.test_opora_graph_proposals import accept, proposal
from database.repositories.opora_changesets import ChangesetRepository

empty_graphs = initial_fixture


def graph_accept(graphs, plan):
    return accept(graphs, proposal(graphs, plan=plan))


def graph_change(graphs, plan):
    changes = OporaGraphChanges(graphs.service)
    context = changes.specifications.context("draft", "draft")
    item = changes.create({**SCOPE, "parentRevision": context["acceptedHead"],
                           "expectedGraphDigest": context["graphDigest"],
                           "subject": "Reviewed graph change", "plan": plan}, AGENT)
    context = changes.specifications.context("draft", "draft")
    return OporaGraphChangeAcceptance(graphs.service).accept(item["id"], {
        **SCOPE, "expectedAcceptedHead": context["acceptedHead"],
        "expectedGraphDigest": context["graphDigest"], "adoptBaseGraphDigest": None,
        "reviewedChangesId": item["id"]}, HUMAN)


def scoped(graphs, node_id, origin, current=None, **kwargs):
    return validate_accepted_lineage(graphs.service.db_for("draft"), "draft", "draft", node_id,
                                     origin, current or origin, **kwargs)


def seeded_graph(graphs):
    accepted = graph_accept(graphs, {"nodes": [{"ref": "a", "kind": "node", "name": "A"},
                                               {"ref": "b", "kind": "node", "name": "B"}]})
    return accepted, OporaGraphProposals(graphs.service)


def test_same_revision_and_unrelated_graph_and_spec_changes_pass(empty_graphs):
    graphs = empty_graphs
    origin, proposals = seeded_graph(graphs)
    target = proposals.read("draft", "draft", origin["proposalId"])["refs"]["a"]
    assert scoped(graphs, target, origin["id"])["checkedRevisions"] == [origin["id"]]

    unrelated = proposals.read("draft", "draft", origin["proposalId"])["refs"]["b"]
    change = propose_spec(graphs.service, nodes=(unrelated,), goal="Unrelated accepted edit")
    edited = accept_spec(graphs.service, change, origin["id"])
    later = graph_accept(graphs, {"nodes": [{"ref": "c", "kind": "node", "name": "C"}]})

    result = scoped(graphs, target, origin["id"], later["id"])
    assert result["acceptedScopeUnchanged"] is True
    assert len(result["scopedAcceptedDigest"]) == 64
    assert result["checkedRevisions"] == [origin["id"], edited["id"], later["id"]]
    assert result["checkedCount"] == 3
    with pytest.raises(ValueError, match="configured bound"):
        scoped(graphs, target, origin["id"], later["id"], max_steps=2)


def test_related_specification_change_and_later_edit_is_rejected(empty_graphs):
    graphs = empty_graphs
    origin, proposals = seeded_graph(graphs)
    target = proposals.read("draft", "draft", origin["proposalId"])["refs"]["a"]
    first = accept_spec(graphs.service, propose_spec(graphs.service, nodes=(target,), goal="Changed"), origin["id"])
    later = accept_spec(graphs.service, propose_spec(graphs.service, nodes=(target,), goal="Later"), first["id"])
    with pytest.raises(ValueError, match="scope changed"):
        scoped(graphs, target, origin["id"], later["id"])


def test_selected_node_change_and_restore_is_rejected(empty_graphs):
    graphs = empty_graphs
    origin, proposals = seeded_graph(graphs)
    refs = proposals.read("draft", "draft", origin["proposalId"])["refs"]
    target = refs["a"]
    origin_digest = scoped(graphs, target, origin["id"])["scopedAcceptedDigest"]
    graph_change(graphs, {"updateNodes": [{"id": target, "fields": {"name": "Changed"}}]})
    restored = graph_change(graphs, {"updateNodes": [{"id": target, "fields": {"name": "A"}}]})
    endpoint = scoped(graphs, target, restored["id"], restored["id"])
    assert endpoint["scopedAcceptedDigest"] == origin_digest
    with pytest.raises(ValueError, match="scope changed"):
        scoped(graphs, target, origin["id"], restored["id"])


def test_incident_edge_insert_then_remove_is_rejected(empty_graphs):
    graphs = empty_graphs
    origin, proposals = seeded_graph(graphs)
    refs = proposals.read("draft", "draft", origin["proposalId"])["refs"]
    target = refs["a"]
    origin_digest = scoped(graphs, target, origin["id"])["scopedAcceptedDigest"]
    inserted = graph_change(graphs, {"nodes": [{"ref": "child", "kind": "node", "name": "Child",
                                                 "parent": f"@{target}"}],
                                     "edges": [{"from": f"@{target}", "to": "child", "port": "next"}]})
    manifest = proposals.repository("draft", "draft").read(inserted["graphManifestId"], manifest=True)
    child = next(node["id"] for node in manifest["graph"]["nodes"] if node["name"] == "Child")
    edge = next(item["id"] for item in manifest["graph"]["edges"] if item["source"] == target)
    removed = graph_change(graphs, {"removeNodes": [child], "removeEdges": [edge]})
    endpoint = scoped(graphs, target, removed["id"], removed["id"])
    assert endpoint["scopedAcceptedDigest"] == origin_digest
    with pytest.raises(ValueError, match="scope changed"):
        scoped(graphs, target, origin["id"], removed["id"])


def test_selected_document_owner_workspace_change_is_rejected(empty_graphs):
    graphs = empty_graphs
    origin, proposals = seeded_graph(graphs)
    target = proposals.read("draft", "draft", origin["proposalId"])["refs"]["a"]
    db = graphs.service.db_for("draft")
    repo = ChangesetRepository(db, "draft", "draft")
    content = {key: value for key, value in origin.items() if key != "id"}
    documents = copy.deepcopy(content["documents"])
    next(document for document in documents if document["nodeId"] == target)["ownerWorkspace"] = "architecture"
    content.update(kind="graph-acceptance", parentRevision=origin["id"], proposalId="d" * 40,
                   documents=documents)
    with db:
        db.execute("BEGIN IMMEDIATE")
        changed_owner = repo.insert(content)
        repo.advance(origin["id"], changed_owner["id"])
    with pytest.raises(ValueError, match="scope changed"):
        scoped(graphs, target, origin["id"], changed_owner["id"])


@pytest.mark.parametrize("origin,current", [("f" * 40, "f" * 40), ("A" * 40, "A" * 40), ("0" * 39, "0" * 39)])
def test_rejects_malformed_or_non_descendant_endpoints(empty_graphs, origin, current):
    graphs = empty_graphs
    accepted, proposals = seeded_graph(graphs)
    target = proposals.read("draft", "draft", accepted["proposalId"])["refs"]["a"]
    with pytest.raises(ValueError):
        scoped(graphs, target, origin, current)


def test_rejects_bad_bounds_stale_head_and_does_not_mutate_database(empty_graphs):
    graphs = empty_graphs
    accepted, proposals = seeded_graph(graphs)
    target = proposals.read("draft", "draft", accepted["proposalId"])["refs"]["a"]
    db = graphs.service.db_for("draft")
    before = copy.deepcopy([tuple(row) for row in db.execute(
        "SELECT project_id,workspace_id,id,content FROM opora_spec_revisions ORDER BY id")])
    for value in (True, False, 0, 257, 1.0, "2"):
        with pytest.raises(ValueError, match="max_steps"):
            scoped(graphs, target, accepted["id"], max_steps=value)
    with pytest.raises(ValueError, match="workspace head"):
        scoped(graphs, target, accepted["id"], "1" * 40)
    assert db.in_transaction is False
    assert [tuple(row) for row in db.execute(
        "SELECT project_id,workspace_id,id,content FROM opora_spec_revisions ORDER BY id")] == before


def test_rejects_legacy_revision_without_manifest(empty_graphs):
    graphs = empty_graphs
    service = graphs.service
    view = service.view("draft", "draft")
    service.save_graph("draft", "draft", {"nodes": [node("a")], "edges": []}, view["digest"])
    baseline(service)
    accepted = OporaChangesets(service).context("draft", "draft")["acceptedHead"]
    with pytest.raises(ValueError, match="no graph manifest"):
        validate_accepted_lineage(service.db_for("draft"), "draft", "draft", "a", accepted, accepted)


def test_rejects_broken_parent_and_corrupt_manifest(empty_graphs):
    graphs = empty_graphs
    origin, proposals = seeded_graph(graphs)
    target = proposals.read("draft", "draft", origin["proposalId"])["refs"]["a"]
    db = graphs.service.db_for("draft")
    repo = ChangesetRepository(db, "draft", "draft")
    malformed = {key: value for key, value in origin.items() if key != "id"}
    malformed["kind"] = "graph-acceptance"
    malformed["parentRevision"] = "f" * 40
    malformed["proposalId"] = "e" * 40
    with db:
        db.execute("BEGIN IMMEDIATE")
        broken = repo.insert(malformed)
        repo.advance(origin["id"], broken["id"])
    with pytest.raises(ValueError):
        scoped(graphs, target, origin["id"], broken["id"])

    db.execute("UPDATE opora_spec_refs SET accepted_id=? WHERE project_id=? AND workspace_id=?",
               (origin["id"], "draft", "draft"))
    db.execute("UPDATE opora_graph_manifests SET content=? WHERE project_id=? AND workspace_id=? AND id=?",
               (canonical({"corrupt": True}), "draft", "draft", origin["graphManifestId"]))
    with pytest.raises(ValueError, match="integrity"):
        scoped(graphs, target, origin["id"])
