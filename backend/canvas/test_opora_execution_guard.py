"""Enrollment blocks typed state mutations without freezing unrelated cards."""
import copy

import pytest

from backend.canvas.opora_execution_guard import state_write
from backend.canvas.test_opora_executions import authority, claim, service  # noqa: F401
from backend.editor.agent_memory.desktop_v3_state import default_state


@pytest.mark.parametrize("kind", ["node", "remove", "edge", "decision", "typed"])
def test_guard_rejects_all_enrolled_state_effects(authority, service, kind):
    claim(authority)
    before = default_state()
    before["nodes"] = {"a": {"flag": True}}
    after = copy.deepcopy(before)
    if kind == "node":
        after["nodes"]["a"]["flag"] = False
    elif kind == "remove":
        del after["nodes"]["a"]
    elif kind == "edge":
        after.setdefault("edges", {})["ab"] = {"summary": "Result"}
    elif kind == "decision":
        after["decisions"].append({"nodeId": "a", "text": "Done"})
    else:
        after["nodes"]["a"]["flag"] = 1
    graph = {"edges": [{"id": "ab", "source": "a", "target": "b"}]}
    for actor in ("agent", "system", "unknown"):
        with pytest.raises(ValueError, match="receipts"):
            state_write(service.db_for("draft"), "draft", "draft", before, after, graph, actor)
    state_write(service.db_for("draft"), "draft", "draft", before, after, graph, "human")


def test_unrelated_state_changes_remain_available(authority, service):
    claim(authority)
    before = default_state()
    after = copy.deepcopy(before)
    after["nodes"]["b"] = {"phase": "discover"}
    state_write(service.db_for("draft"), "draft", "draft", before, after, {"edges": []}, "agent")


def test_server_close_changes_only_the_done_mark():
    from backend.canvas.opora_execution_guard import SKELETON, closes_only
    done = {"confirmed": True, "by": "opora", "at": "2026-10-31T12:00:00Z", "note": ""}
    card = {"phase": "build", "criteria": [], "steps": [], "notes": "x"}
    assert closes_only(card, {**card, "done": done})
    assert closes_only(None, {**SKELETON, "done": done})
    assert closes_only(card, card)
    assert not closes_only(card, {**card, "notes": "y", "done": done})
    assert not closes_only(card, {**card, "done": {**done, "confirmed": False}})
    assert not closes_only({**card, "done": done}, None)
