"""Pojistka confirmed_reopen: enforce drží změnu potvrzené karty, warn ji pustí a zapíše, přehrání záznamu nezávisí na režimu."""
import pytest

from backend.app import error_log, errors, guards
from backend.canvas.opora_graph_change_safety import preflight
from backend.canvas.test_graph_card import node
from backend.canvas.test_opora_graph_change_state import canvas as canvas  # noqa: PLC0414
from backend.canvas.test_opora_graph_change_state import graph, install, review
from backend.editor.agent_memory.desktop_v3_state import default_done, default_state
from backend.editor.node.test_removals import state_node


@pytest.fixture
def closed(canvas):
    errors.configure(canvas.root)
    guards.configure(canvas.root)
    state = default_state()
    state["nodes"] = {"closed": state_node(done={**default_done(), "confirmed": True, "at": "2026-10-21T00:00:00Z"})}
    install(canvas, state)
    yield canvas, state, graph(node("closed")), graph(node("closed", name="Changed"))
    error_log.drain()
    guards.configure(None)
    errors.configure(None)


def test_enforce_blocks_and_warn_lets_change_through(closed):
    canvas, _, before, after = closed
    with pytest.raises(ValueError, match="reopen confirmed"):
        review(canvas, before, after)
    guards.set_mode("confirmed_reopen", "draft", "warn", ("human", None), "srdce opravuje uzavřenou kartu")
    assert review(canvas, before, after)["checkedNodeIds"] == ["closed"]
    error_log.drain()
    messages = [r["message"] for r in errors.read() if r["kind"] == "blocked"]
    assert any(m.startswith("pojistka confirmed_reopen ve warn") for m in messages)
    assert any(m.startswith("Změna grafu sahá na potvrzené karty") for m in messages)


def test_replay_of_stored_record_ignores_mode(closed):
    _, state, before, after = closed
    guards.set_mode("confirmed_reopen", "", "enforce", ("human", None), "výchozí")
    # validate_record přehrává uložený záznam bez projektu: týž vstup už prošel živou cestou
    assert preflight(before, before, after, after, state, set(), set())[0] == ["closed"]
