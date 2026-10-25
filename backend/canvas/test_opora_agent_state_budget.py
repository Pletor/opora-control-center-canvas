"""Agent-state build budget: project-wide facts once per build, never once per card (N+1 guard).

On a live plan of ~150 cards the build took 5-13 s under the project locks because every card's
claim context re-read the accepted context, stored state, accepted graph and live content. The
counts below fail as soon as one of them goes back into the per-card loop."""
import time
from collections import Counter

import pytest

from backend.canvas import opora_changesets, opora_content_execution, opora_graph_execution
from backend.canvas.opora_agent_state import AgentState
from backend.canvas.test_opora_agent_state import no_pull_module as no_pull_module  # noqa: PLC0414
from backend.canvas.test_opora_agent_state_card_page import FILLERS, big_plan
from backend.canvas.test_opora_changesets import SCOPE
from backend.canvas.test_opora_changesets import service as service  # noqa: PLC0414
from backend.editor.agent_memory import desktop_v3_state
from backend.editor.agent_packet import specification_context

BUDGET_SECONDS = 4.0  # generous for slow CI; the per-card rebuild took several times longer here


def _count(monkeypatch, calls, owner, name):
    original = getattr(owner, name)

    def counted(*args, **kwargs):
        calls[name] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(owner, name, counted)


def test_one_build_reads_project_wide_facts_once(service, monkeypatch):
    big_plan(service)
    calls = Counter()
    _count(monkeypatch, calls, opora_changesets.OporaChangesets, "_context")
    _count(monkeypatch, calls, desktop_v3_state.DesktopV3State, "_current")
    _count(monkeypatch, calls, opora_graph_execution, "_require")
    _count(monkeypatch, calls, opora_content_execution, "_accepted")
    _count(monkeypatch, calls, opora_content_execution, "_live")
    _count(monkeypatch, calls, specification_context, "_card")
    document = AgentState(service).read(**SCOPE)
    assert document["cardsTotal"] > len(FILLERS)
    assert calls["_context"] == calls["_current"] == 1
    assert calls["_require"] == calls["_accepted"] == 1 and calls["_live"] <= 1  # the claim checks did run
    assert 0 < calls["_card"] <= document["cardsTotal"]  # each related card captured once, shared by every capture


def test_build_stays_under_budget_and_the_cache_ends_with_it(service):
    big_plan(service)
    reader = AgentState(service)
    first = reader.read(**SCOPE)
    started = time.perf_counter()
    second = reader.read(**SCOPE)
    assert time.perf_counter() - started < BUDGET_SECONDS
    assert {key: value for key, value in second.items() if key != "generatedAt"} == \
        {key: value for key, value in first.items() if key != "generatedAt"}
    assert getattr(service._local, "steady", {}) == {}  # nothing outlives the build


def test_steady_value_memoizes_results_and_refusals_only_inside_the_block(service):
    calls = Counter()

    def compute():
        calls["ok"] += 1
        return {"value": calls["ok"]}

    def refuse():
        calls["refused"] += 1
        raise ValueError("no")

    assert service.steady_value("draft", ("k",), compute) != service.steady_value("draft", ("k",), compute)
    with service.lock_for("draft"), service.steady_reads("draft"):
        assert service.steady_value("draft", ("k",), compute) is service.steady_value("draft", ("k",), compute)
        for _ in range(2):
            with pytest.raises(ValueError, match="no"):
                service.steady_value("draft", ("r",), refuse)
    assert calls == {"ok": 3, "refused": 1}
