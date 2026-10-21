"""Graph edits retain field-level accepted/working separation and immutable review."""
from copy import deepcopy

import pytest

from backend.canvas.opora_graph_change_acceptance import OporaGraphChangeAcceptance
from backend.canvas.opora_graph_changes import OporaGraphChanges
from backend.canvas.test_opora_changesets import AGENT, HUMAN, SCOPE
from backend.canvas.test_opora_graph_proposals import accept, graphs, proposal, service

__all__ = ["graphs", "service"]


@pytest.fixture
def edits(graphs):
    accept(graphs, proposal(graphs))
    return OporaGraphChanges(graphs.service)


def change(edits, plan):
    context = edits.specifications.context("draft", "draft")
    return edits.create({**SCOPE, "parentRevision": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
                         "subject": "Reviewed graph change", "plan": plan}, AGENT)


def approve(edits, item, **overrides):
    context = edits.specifications.context("draft", "draft")
    return OporaGraphChangeAcceptance(edits.service).accept(item["id"], {**SCOPE,
        "expectedAcceptedHead": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
        "adoptBaseGraphDigest": None, "reviewedChangesId": item["id"], **overrides}, HUMAN)


def working_edit(service, node_id, **fields):
    view = service.view("draft", "draft")
    graph = deepcopy(view["graph"])
    next(node for node in graph["nodes"] if node["id"] == node_id).update(fields)
    service.save_graph("draft", "draft", graph, view["digest"], allow_removal=True)


def test_field_patch_does_not_adopt_unrelated_working_drift(edits, service):
    working_edit(service, "a", name="Unaccepted rename", purpose="Unaccepted purpose")
    working_edit(service, "b", purpose="Other unaccepted content")
    item = change(edits, {"updateNodes": [{"id": "a", "fields": {"name": "Reviewed rename"}}]})
    accepted = {node["id"]: node for node in item["acceptedResultGraph"]["nodes"]}
    working = {node["id"]: node for node in item["resultGraph"]["nodes"]}
    assert accepted["a"]["name"] == working["a"]["name"] == "Reviewed rename"
    assert accepted["a"].get("purpose") != working["a"]["purpose"]
    assert accepted["b"].get("purpose") != working["b"]["purpose"]
    assert next(node for node in service.view("draft", "draft")["graph"]["nodes"] if node["id"] == "a")["name"] == "Unaccepted rename"
    approve(edits, item)
    assert service.view("draft", "draft")["graph"] == item["resultGraph"]


def test_independent_field_rebase_and_target_conflict(edits, service):
    item = change(edits, {"updateNodes": [{"id": "a", "fields": {"name": "Reviewed"}}]})
    working_edit(service, "b", purpose="Unrelated")
    context = edits.specifications.context("draft", "draft")
    moved = edits.rebase(item["id"], {**SCOPE, "expectedAcceptedHead": context["acceptedHead"],
                                    "expectedGraphDigest": context["graphDigest"]}, AGENT)
    assert moved["supersedes"] == item["id"] and moved["id"] != item["id"]
    working_edit(service, "a", name="Conflicting")
    context = edits.specifications.context("draft", "draft")
    with pytest.raises(ValueError, match="Affected graph"):
        edits.rebase(moved["id"], {**SCOPE, "expectedAcceptedHead": context["acceptedHead"],
                                 "expectedGraphDigest": context["graphDigest"]}, AGENT)


def test_removal_of_already_working_deleted_accepted_node(edits, service):
    view = service.view("draft", "draft")
    graph = deepcopy(view["graph"])
    graph["nodes"] = [node for node in graph["nodes"] if node["id"] != "a"]
    service.save_graph("draft", "draft", graph, view["digest"], allow_removal=True)
    item = change(edits, {"removeNodes": ["a"]})
    removed = item["changes"]["nodes"][0]
    assert removed["acceptedBefore"] and removed["workingBefore"] is None
    revision = approve(edits, item)
    assert "a" not in {doc["nodeId"] for doc in revision["documents"]}


@pytest.mark.parametrize("plan", [
    {"updateNodes": [{"id": "a", "fields": {"kind": "area"}}]},
    {"updateNodes": [{"id": "a", "fields": {}}]},
    {"removeNodes": ["a", "a"]}, {"removeNodes": ["unknown"]},
    {"removeNodes": ["a"], "updateNodes": [{"id": "a", "fields": {"name": "X"}}]},
    {"updateNodes": [{"id": "a", "fields": {"parentId": "@b"}}]},
])
def test_invalid_operations_rejected(edits, plan):
    with pytest.raises(ValueError):
        change(edits, plan)


def test_explicit_review_and_historical_replay(edits):
    first = change(edits, {"updateNodes": [{"id": "a", "fields": {"name": "First"}}]})
    with pytest.raises(ValueError, match="Explicit human"):
        approve(edits, first, reviewedChangesId="wrong")
    original = approve(edits, first)
    later = approve(edits, change(edits, {"updateNodes": [{"id": "a", "fields": {"name": "Later"}}]}))
    assert approve(edits, first) == original
    assert edits.specifications.context("draft", "draft")["acceptedHead"] == later["id"]


def test_mixed_addition_and_edit_preserve_stable_ids_and_default_specs(edits, service):
    item = change(edits, {"updateNodes": [{"id": "a", "fields": {"name": "Reviewed"}}],
                         "nodes": [{"ref": "fresh", "kind": "node", "name": "Fresh"}],
                         "edges": [{"from": "@a", "to": "fresh", "port": "next"}]})
    assert edits.repository("draft", "draft").read(item["id"])["refs"] == item["refs"]
    working_edit(service, "b", purpose="Unrelated")
    context = edits.context(**SCOPE)
    rebased = edits.rebase(item["id"], {**SCOPE, "expectedAcceptedHead": context["acceptedHead"],
                                      "expectedGraphDigest": context["graphDigest"]}, AGENT)
    assert rebased["refs"] == item["refs"]
    result = approve(edits, rebased)
    spec = next(doc for doc in result["documents"] if doc["nodeId"] == item["refs"]["fresh"])
    assert spec["revision"] == 1 and spec["fields"] == {"goal": "", "non_goals": "", "acceptance": ""}
