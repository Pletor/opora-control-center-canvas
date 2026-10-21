"""Pure graph changes cover closure, patch conflicts and dependency-context adoption."""
from copy import deepcopy

import pytest

from backend.canvas.opora_graph_change_build import build
from backend.canvas.test_graph_card import node
from backend.canvas.test_project_architecture import domain, page


def graph():
    return {"nodes": [node("sector", kind="sector"), node("child", parent_id="sector"), node("other")],
            "edges": [{"id": "edge", "source": "child", "target": "other", "port": "next"}]}


@pytest.mark.parametrize("plan,missing", [({"removeNodes": ["sector"]}, "child"),
    ({"removeNodes": ["sector", "child"]}, "edge")])
def test_exact_closure(plan, missing):
    with pytest.raises(ValueError, match=missing):
        build(graph(), graph(), plan, {})


def test_reparent_and_rewire_explicitly_resolve_removal_dependencies():
    result = build(graph(), graph(), {"removeNodes": ["sector"],
        "updateNodes": [{"id": "child", "fields": {"parentId": None}}]}, {})
    assert {item["id"] for item in result["resultGraph"]["nodes"]} == {"child", "other"}
    result = build(graph(), graph(), {"removeNodes": ["child"],
        "updateEdges": [{"id": "edge", "source": "sector", "target": "other", "port": "next"}]}, {})
    assert result["resultGraph"]["edges"][0]["source"] == "sector"


def test_noop_edge_update_is_rejected_even_with_effective_node_change():
    with pytest.raises(ValueError, match="Every graph update"):
        build(graph(), graph(), {"updateNodes": [{"id": "child", "fields": {"name": "Changed"}}],
            "updateEdges": [{"id": "edge", "source": "child", "target": "other", "port": "next"}]}, {})


def test_architecture_adoption_replaces_only_accepted_dependency():
    accepted = {"nodes": [domain(), page(), node("content")], "edges": []}
    working = deepcopy(accepted)
    working["nodes"][0]["name"] = "New shared architecture name"
    working["nodes"][2]["name"] = "Unreviewed content name"
    result = build(accepted, working, {"adoptArchitectureContext": True}, {})
    assert result["acceptedResultGraph"]["nodes"][0]["name"] == "New shared architecture name"
    assert result["acceptedResultGraph"]["nodes"][2]["name"] == "content"
    assert result["resultGraph"] == working
    assert result["changes"]["architectureContext"]["proposedAccepted"] == result["changes"]["architectureContext"]["workingBefore"]
    with pytest.raises(ValueError, match="no effective"):
        build(accepted, accepted, {"adoptArchitectureContext": True}, {})
    working["nodes"][0]["name"] = "Another architecture edit"
    with pytest.raises(ValueError, match="Affected graph"):
        build(accepted, working, {"adoptArchitectureContext": True}, {}, previous=result)


def test_architecture_edit_remains_forbidden():
    original = {"nodes": [domain(), page()], "edges": []}
    with pytest.raises(ValueError, match="architecture"):
        build(original, original, {"updateNodes": [{"id": "app", "fields": {"name": "Illegal"}}]}, {})


def test_rebase_keeps_added_ids_and_field_preimages():
    original = graph()
    result = build(original, original, {"updateNodes": [{"id": "child", "fields": {"name": "Reviewed"}}],
        "nodes": [{"ref": "fresh", "kind": "node", "name": "Fresh", "parent": "@sector"}]}, {"nodes": {}})
    updated = deepcopy(original)
    updated["nodes"][2]["name"] = "Unrelated"
    rebased = build(updated, updated, result["plan"], {}, previous=result)
    assert rebased["refs"] == result["refs"]
    updated["nodes"][1]["name"] = "Conflicting"
    with pytest.raises(ValueError, match="Affected graph"):
        build(updated, updated, result["plan"], {}, previous=result)
