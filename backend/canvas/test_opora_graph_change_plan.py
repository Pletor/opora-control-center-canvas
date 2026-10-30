"""Hranice návrhu grafu od srdce (`heart_scope`): u existujícího uzlu jen `memberOf`, vazby vůbec."""
import pytest

from backend.canvas.opora_graph_change_plan import HeartEditRefused, heart_scope, normalize


def test_member_of_only_passes_and_stays_a_valid_plan():
    plan = {"updateNodes": [{"id": "n1", "fields": {"memberOf": "a1"}}, {"id": "n2", "fields": {"memberOf": None}}]}
    heart_scope(plan)
    assert normalize(plan)["updateNodes"] == plan["updateNodes"]


def test_additions_and_removals_of_existing_heart_commands_still_pass():
    heart_scope({"nodes": [{"ref": "a", "kind": "node", "name": "A"}], "edges": []})  # plan
    heart_scope({"removeNodes": ["n1"], "removeEdges": ["e1"], "adoptArchitectureContext": True})  # prune, unlink


@pytest.mark.parametrize("plan", [
    {"updateNodes": [{"id": "n1", "fields": {"memberOf": "a1", "name": "Jinak"}}]},
    {"updateNodes": [{"id": "n1", "fields": {"parentId": "s1"}}]},
    {"updateNodes": [{"id": "n1", "fields": {"x": 10, "y": 20}}]},
    {"updateNodes": [{"id": "n1"}]},
    {"updateEdges": [{"id": "e1", "source": "a", "target": "b", "port": "next"}]},
])
def test_any_other_heart_edit_is_refused_with_a_code(plan):
    with pytest.raises(HeartEditRefused) as refused:
        heart_scope(plan)
    assert refused.value.status == 422 and refused.value.body()["code"] == "heart_edit_scope"
    assert "memberOf" in refused.value.body()["hint"]
