"""Oprávnění odděleně od původce (docs/plna-autonomie-agenta.md §2)."""
import pytest

from backend.canvas import authority
from backend.canvas.activity_log import HumanRequired, require_authority, require_human


def test_resolve_never_lifts_unknown():
    assert authority.resolve("human", False) == "human"
    assert authority.resolve("agent", False) == "agent"
    assert authority.resolve("agent", True) == "human"
    assert authority.resolve("unknown", True) == "unknown"


def test_gate_outside_request_keeps_agent_out():
    assert authority.acts_as_human("human")
    assert not authority.acts_as_human("agent")
    with pytest.raises(HumanRequired):
        require_authority("agent", "x")


def test_agent_with_full_autonomy_passes_and_marks_use():
    state, token = authority.begin("agent", "human", "p")
    try:
        assert not state.used
        assert authority.can_act("agent") and not state.used  # příznak neoznačuje
        require_authority("agent", "x")
        assert state.used
        # Výjimky §4 zůstávají člověku i při plné autonomii.
        with pytest.raises(HumanRequired):
            require_human("agent", "x")
        # Jiný původce než agent požadavku autonomii nedědí.
        assert not authority.acts_as_human("unknown")
    finally:
        authority.end(token)
    assert not authority.acts_as_human("agent")


def test_agent_without_autonomy_is_refused():
    state, token = authority.begin("agent", "agent", "p")
    try:
        with pytest.raises(HumanRequired):
            require_authority("agent", "x")
        assert not state.used
    finally:
        authority.end(token)
