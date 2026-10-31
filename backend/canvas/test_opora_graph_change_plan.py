"""Hranice návrhu grafu od srdce (`heart_scope`): u existujícího uzlu jen `memberOf` a `order`, vazby vůbec."""
import pytest

from backend.canvas.opora_graph_change_plan import HeartEditRefused, apply, heart_scope, normalize


def test_member_of_only_passes_and_stays_a_valid_plan():
    plan = {"updateNodes": [{"id": "n1", "fields": {"memberOf": "a1"}}, {"id": "n2", "fields": {"memberOf": None}}]}
    heart_scope(plan)
    assert normalize(plan)["updateNodes"] == plan["updateNodes"]


def test_order_passes_and_null_removes_it():
    plan = {"updateNodes": [{"id": "n1", "fields": {"order": 101}}, {"id": "n2", "fields": {"order": None, "memberOf": "a1"}}]}
    heart_scope(plan)
    normalized = normalize(plan)
    graph = {"nodes": [{"id": "n1", "kind": "node"}, {"id": "n2", "kind": "sector", "order": 205}], "edges": []}
    assert apply(graph, normalized)["nodes"] == [{"id": "n1", "kind": "node", "order": 101},
                                                 {"id": "n2", "kind": "sector", "memberOf": "a1"}]


@pytest.mark.parametrize("value", [0, 10000, True, 1.5, "101"])
def test_order_out_of_range_is_not_a_valid_plan(value):
    with pytest.raises(ValueError):
        normalize({"updateNodes": [{"id": "n1", "fields": {"order": value}}]})


def test_additions_and_removals_of_existing_heart_commands_still_pass():
    heart_scope({"nodes": [{"ref": "a", "kind": "node", "name": "A"}], "edges": []})  # plan
    heart_scope({"removeNodes": ["n1"], "removeEdges": ["e1"], "adoptArchitectureContext": True})  # prune, unlink


@pytest.mark.parametrize("plan", [
    {"updateNodes": [{"id": "n1", "fields": {"memberOf": "a1", "name": "Jinak"}}]},
    {"updateNodes": [{"id": "n1", "fields": {"order": 101, "purpose": "Jinak"}}]},
    {"updateNodes": [{"id": "n1", "fields": {"parentId": "s1"}}]},
    {"updateNodes": [{"id": "n1", "fields": {"x": 10, "y": 20}}]},
    {"updateNodes": [{"id": "n1"}]},
    {"updateEdges": [{"id": "e1", "source": "a", "target": "b", "port": "next"}]},
])
def test_any_other_heart_edit_is_refused_with_a_code(plan):
    with pytest.raises(HeartEditRefused) as refused:
        heart_scope(plan)
    assert refused.value.status == 422 and refused.value.body()["code"] == "heart_edit_scope"
    assert "memberOf" in refused.value.body()["hint"] and "order" in refused.value.body()["hint"]
