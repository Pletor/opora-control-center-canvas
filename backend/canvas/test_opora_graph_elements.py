"""Semantic graph proposals keep reviewed fields and immutable shared context."""
from copy import deepcopy

import pytest

from backend.canvas.opora_graph_build import prepare
from backend.canvas.opora_graph_change_build import build
from backend.canvas.opora_graph_records import combined
from backend.canvas.test_opora_graph_change_carries import REWIRE
from backend.canvas.test_opora_graph_change_build import graph
from backend.canvas.test_opora_graph_changes import approve, change, edits
from backend.canvas.test_opora_graph_proposals import accept, graphs, proposal, service


def test_semantic_addition_and_change_retain_ports_and_explicit_fields():
    base = graph()
    result = build(base, base, {"updateEdges": [{**REWIRE, "relation": "uses", "reason": "Tenant isolation"}]}, {})
    edge = result["resultGraph"]["edges"][0]
    assert edge["relation"] == "uses" and edge["reason"] == "Tenant isolation"
    assert result["changes"]["edges"][0]["fields"] == ["source", "target", "port", "relation", "reason"]
    assert result["preconditions"]["working"]["edges"]["edge"]["relation"] == {"present": False, "value": None}
    removed = build(result["resultGraph"], result["resultGraph"], {
        "updateEdges": [{**REWIRE, "relation": None, "reason": None}]}, {})
    assert "relation" not in removed["resultGraph"]["edges"][0]
    assert "reason" not in removed["resultGraph"]["edges"][0]
    addition = prepare({"edges": [{"from": "@child", "to": "@other", "port": "action", "relation": "evidences", "reason": "Test result"}]},
                       {**base, "edges": []}, {})
    assert addition["additions"]["edges"][0]["relation"] == "evidences"


def test_semantic_relation_survives_proposal_acceptance_and_native_change(graphs, service):
    item = proposal(graphs, plan={"edges": [{"from": "@a", "to": "@b", "port": "action", "relation": "uses", "reason": "Shared identity"}]})
    [edge] = item["additions"]["edges"]
    assert graphs.read("draft", "draft", item["id"])["additions"]["edges"] == [edge]
    revision = accept(graphs, item)
    manifest = graphs.repository("draft", "draft").read(revision["graphManifestId"], manifest=True)
    assert edge in combined(manifest)["edges"]
    assert edge in service.view("draft", "draft")["graph"]["edges"]


def test_native_semantic_patch_and_cycle_rejection_are_atomic(edits, service):
    item = change(edits, {"draftVersion": 3, "edges": [
        {"from": "@a", "to": "@b", "port": "action", "relation": "requires"}]})
    approve(edits, item)
    edge = item["additions"]["edges"][0]
    before_graph = deepcopy(service.view("draft", "draft")["graph"])
    before_proposals = edits.list("draft", "draft")
    with pytest.raises(ValueError, match="cyklus"):
        change(edits, {"draftVersion": 3, "edges": [
            {"from": "@b", "to": "@a", "port": "rule", "relation": "requires"}]})
    assert edits.list("draft", "draft") == before_proposals
    assert service.view("draft", "draft")["graph"] == before_graph
    changed = change(edits, {"draftVersion": 3, "updateEdges": [{
        **{key: edge[key] for key in ("id", "source", "target", "port")}, "relation": "communicates_with", "reason": "Bidirectional protocol"}]})
    pinned = deepcopy(changed)
    approve(edits, changed)
    assert edits.read("draft", "draft", changed["id"])["plan"] == pinned["plan"]
    live = next(row for row in service.view("draft", "draft")["graph"]["edges"] if row["id"] == edge["id"])
    assert live["relation"] == "communicates_with" and live["reason"] == "Bidirectional protocol"


def test_typed_shared_context_is_pinned_by_explicit_adoption(edits, service):
    architecture = service.architecture.read("draft")
    typed = deepcopy(architecture["graph"])
    typed["nodes"][0]["element"] = {"kind": "service"}
    service.architecture.save({"project": "draft", "workspace": "draft", "expectedRevision": architecture["revision"], "graph": typed}, actor="agent")
    item = change(edits, {"adoptArchitectureContext": True})
    revision = approve(edits, item)
    manifest = edits.repository("draft", "draft").read(revision["graphManifestId"], manifest=True)
    pinned = deepcopy(manifest)
    assert next(node for node in combined(manifest)["nodes"] if node["id"] == "app")["element"] == {"kind": "service"}
    current = service.architecture.read("draft")
    typed["nodes"][0]["element"] = {"kind": "process"}
    service.architecture.save({"project": "draft", "workspace": "draft", "expectedRevision": current["revision"], "graph": typed}, actor="agent")
    assert edits.repository("draft", "draft").read(revision["graphManifestId"], manifest=True) == pinned


def test_shared_element_edits_cannot_bypass_project_architecture(edits, service):
    before = deepcopy(service.view("draft", "draft")["graph"])
    with pytest.raises(ValueError, match="shared architecture"):
        change(edits, {"draftVersion": 3, "updateNodes": [{"id": "a", "fields": {"element": {"kind": "service"}}}]})
    assert service.view("draft", "draft")["graph"] == before
