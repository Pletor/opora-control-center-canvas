"""Explicit membership survives the current proposal/acceptance protocol."""
from copy import deepcopy

import pytest

from backend.canvas.opora_graph_changes import OporaGraphChanges
from backend.canvas.test_opora_changesets import AGENT, SCOPE
from backend.canvas.test_opora_graph_changes import approve, change, working_edit
from backend.canvas.test_opora_graph_proposals import accept, graphs, proposal, service

__all__ = ["graphs", "service"]


def membership_plan():
    return {"nodes": [
        {"ref": "area", "kind": "area", "name": "Explicit area", "size": {"w": 500, "h": 500}},
        {"ref": "member", "kind": "sector", "name": "Member", "memberOf": "area"},
    ]}


def test_addition_preserves_membership_without_mutating_before_acceptance(graphs, service):
    before = deepcopy(service.view("draft", "draft")["graph"])
    item = proposal(graphs, plan=membership_plan())
    assert service.view("draft", "draft")["graph"] == before
    accept(graphs, item)
    nodes = {node["id"]: node for node in service.view("draft", "draft")["graph"]["nodes"]}
    assert nodes[item["refs"]["member"]]["memberOf"] == item["refs"]["area"]


def test_mixed_proposal_and_explicit_clear_then_removal(graphs, service):
    accept(graphs, proposal(graphs))
    edits = OporaGraphChanges(service)
    item = change(edits, {**membership_plan(), "updateNodes": [{"id": "a", "fields": {"name": "Reviewed"}}]})
    approve(edits, item)
    member, area = item["refs"]["member"], item["refs"]["area"]
    before = deepcopy(service.view("draft", "draft")["graph"])
    with pytest.raises(ValueError):
        change(edits, {"removeNodes": [area]})
    assert service.view("draft", "draft")["graph"] == before
    cleared = change(edits, {"updateNodes": [{"id": member, "fields": {"memberOf": None}}], "removeNodes": [area]})
    approve(edits, cleared)
    nodes = {node["id"]: node for node in service.view("draft", "draft")["graph"]["nodes"]}
    assert area not in nodes and "memberOf" not in nodes[member]


@pytest.mark.parametrize("target", ["missing", "a", "@a", 3, []])
def test_bad_membership_patch_is_atomic(graphs, service, target):
    accept(graphs, proposal(graphs))
    edits = OporaGraphChanges(service)
    before = deepcopy(service.view("draft", "draft")["graph"])
    with pytest.raises(ValueError):
        change(edits, {"updateNodes": [{"id": "b", "fields": {"memberOf": target}}]})
    assert service.view("draft", "draft")["graph"] == before


def test_membership_edit_pins_area_and_preserves_other_working_fields(graphs, service):
    area_proposal = proposal(graphs, plan={"nodes": membership_plan()["nodes"][:1]})
    accept(graphs, area_proposal)
    area = area_proposal["refs"]["area"]
    edits = OporaGraphChanges(service)
    working_edit(service, "b", purpose="Unaccepted working draft")
    item = change(edits, {"updateNodes": [{"id": "b", "fields": {"memberOf": area}}]})
    accepted = {node["id"]: node for node in item["acceptedResultGraph"]["nodes"]}
    working = {node["id"]: node for node in item["resultGraph"]["nodes"]}
    assert accepted["b"]["memberOf"] == working["b"]["memberOf"] == area
    assert accepted["b"].get("purpose") != working["b"]["purpose"]
    assert item["changes"]["nodes"][0]["fields"] == ["memberOf"]
    working_edit(service, area, name="Changed responsibility")
    context = edits.context(**SCOPE)
    with pytest.raises(ValueError, match="Affected graph"):
        edits.rebase(item["id"], {**SCOPE, "expectedAcceptedHead": context["acceptedHead"],
                                 "expectedGraphDigest": context["graphDigest"]}, AGENT)


def test_addition_to_existing_area_pins_its_semantics(graphs, service):
    first = proposal(graphs, plan={"nodes": membership_plan()["nodes"][:1]})
    accept(graphs, first)
    area = first["refs"]["area"]
    item = proposal(graphs, plan={"nodes": [{"ref": "member", "kind": "node", "name": "Member", "memberOf": "@" + area}]})
    assert area in item["anchors"]
    working_edit(service, area, name="Changed responsibility")
    context = graphs.context(**SCOPE)
    with pytest.raises(ValueError, match="anchor"):
        graphs.rebase(item["id"], {**SCOPE, "expectedAcceptedHead": context["acceptedHead"],
                                  "expectedGraphDigest": context["graphDigest"]}, AGENT)
