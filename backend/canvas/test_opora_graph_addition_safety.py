"""Existing additive proposals cannot bypass current completed-card guards."""
import pytest

from backend.canvas.opora_graph_addition_safety import validate_additions
from backend.canvas.test_graph_card import node
from backend.canvas.test_opora_graph_change_state import canvas, install
from backend.editor.agent_memory.desktop_v3_state import default_done, default_state
from backend.editor.node.test_removals import state_node

__all__ = ["canvas"]


def closed(canvas, key="closed"):
    state = default_state()
    state["nodes"][key] = state_node()
    state["nodes"][key]["done"] = {**default_done(), "confirmed": True}
    install(canvas, state)


@pytest.mark.parametrize("source,target", [("closed", "open"), ("open", "closed")])
def test_added_edge_rechecks_both_closed_endpoints(canvas, source, target):
    closed(canvas)
    before = {"nodes": [node("closed"), node("open")], "edges": []}
    after = {**before, "edges": [{"id": "edge", "source": source, "target": target}]}
    with pytest.raises(ValueError, match="reopen"):
        validate_additions(canvas, "draft", "draft", before, after, before, after)


def test_unrelated_closed_node_does_not_prevent_new_root(canvas):
    closed(canvas)
    before = {"nodes": [node("closed")], "edges": []}
    after = {"nodes": [*before["nodes"], node("new")], "edges": []}
    validate_additions(canvas, "draft", "draft", before, after, before, after)


def test_new_child_rechecks_current_confirmed_ancestor(canvas):
    before = {"nodes": [node("closed", kind="sector")], "edges": []}
    after = {"nodes": [*before["nodes"], node("new", parent_id="closed")], "edges": []}
    validate_additions(canvas, "draft", "draft", before, after, before, after)
    closed(canvas)
    with pytest.raises(ValueError, match="reopen"):
        validate_additions(canvas, "draft", "draft", before, after, before, after)


def test_new_area_cannot_change_closed_card_membership(canvas):
    closed(canvas)
    before = {"nodes": [node("closed", x=200, y=200)], "edges": []}
    after = {"nodes": [*before["nodes"], node("area", kind="area", x=0, y=0, size={"w": 1000, "h": 1000})], "edges": []}
    with pytest.raises(ValueError, match="reopen"):
        validate_additions(canvas, "draft", "draft", before, after, before, after)
