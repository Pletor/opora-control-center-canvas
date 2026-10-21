import pytest

from backend.canvas.graph import digest
from backend.canvas.opora_proposal_risk import classify_risk


def test_specification_and_graph_addition_risk_levels():
    spec = {"changes": [{"nodeId": "card", "fields": {"goal": "new"}}]}
    assert classify_risk("spec", spec)["level"] == "elevated"

    addition = {"kind": "graph-additions", "requiresBaseAdoption": False,
                "parentGraphManifestId": "a" * 40}
    assert classify_risk("graph-addition", addition) == {
        "level": "elevated", "reasons": ["graph_addition"],
        "digest": digest({"level": "elevated", "reasons": ["graph_addition"]}),
    }
    initial = {**addition, "requiresBaseAdoption": True, "parentGraphManifestId": None}
    assert classify_risk("graph-addition", initial)["level"] == "critical"


@pytest.mark.parametrize(("plan", "expected", "reasons"), [
    ({"removeNodes": [], "removeEdges": [], "adoptArchitectureContext": False},
     "elevated", ["graph_changed"]),
    ({"removeNodes": ["n"], "removeEdges": [], "adoptArchitectureContext": False},
     "critical", ["graph_changed", "nodes_removed"]),
    ({"removeNodes": [], "removeEdges": ["e"], "adoptArchitectureContext": False},
     "critical", ["edges_removed", "graph_changed"]),
    ({"removeNodes": [], "removeEdges": [], "adoptArchitectureContext": True},
     "critical", ["graph_changed", "shared_architecture_context_adopted"]),
    ({"removeNodes": ["n"], "removeEdges": ["e"], "adoptArchitectureContext": True},
     "critical", ["edges_removed", "graph_changed", "nodes_removed", "shared_architecture_context_adopted"]),
])
def test_graph_change_risk(plan, expected, reasons):
    result = classify_risk("graph-change", {"kind": "graph-changes", "plan": plan})
    assert result["level"] == expected
    assert result["reasons"] == sorted(reasons)


def test_content_mixed_risk_is_order_independent_and_deterministic():
    changes = [
        {"kind": "text", "field": "text"},
        {"kind": "drawing", "field": "scene"},
        {"kind": "config", "field": "materials"},
        {"kind": "config", "field": "actions"},
        {"kind": "config", "field": "rules"},
        {"kind": "config", "field": "blocks"},
        {"kind": "config", "field": "downloadsUrl"},
    ]
    proposal = {"kind": "content-proposal", "requiresBaseContentAdoption": False, "changes": changes}
    first = classify_risk("content", proposal)
    second = classify_risk("content", {**proposal, "changes": list(reversed(changes))})
    assert first == second
    assert first["level"] == "elevated"
    assert first["reasons"] == [
        "control_field_changed:actions", "control_field_changed:blocks",
        "control_field_changed:downloadsUrl", "control_field_changed:rules",
        "drawing_changed", "materials_changed", "text_changed",
    ]
    ordinary = classify_risk("content", {**proposal, "changes": changes[:3]})
    assert ordinary["level"] == "standard"
    assert ordinary["reasons"] == ["drawing_changed", "materials_changed", "text_changed"]
    assert classify_risk("content", {**proposal, "requiresBaseContentAdoption": True})["level"] == "critical"


@pytest.mark.parametrize(("kind", "record"), [
    ("spec", {"kind": "graph-additions", "changes": [{}]}),
    ("graph-addition", {"kind": "graph-changes"}),
    ("graph-change", {"kind": "graph-additions"}),
    ("content", {"kind": "graph-changes"}),
    ("unknown", {"kind": "content-proposal"}),
])
def test_rejects_wrong_or_unknown_native_kind(kind, record):
    with pytest.raises(ValueError):
        classify_risk(kind, record)


def test_rejects_inconsistent_or_unknown_risk_fields():
    with pytest.raises(ValueError):
        classify_risk("graph-addition", {"kind": "graph-additions", "requiresBaseAdoption": False,
                                          "parentGraphManifestId": None})
    with pytest.raises(ValueError):
        classify_risk("graph-change", {"kind": "graph-changes", "plan": {"removeNodes": [],
            "removeEdges": [], "adoptArchitectureContext": 1}})
    with pytest.raises(ValueError):
        classify_risk("content", {"kind": "content-proposal", "requiresBaseContentAdoption": False,
            "changes": [{"kind": "config", "field": "unreviewed-control"}]})
