"""Map holes as agent work in agent-state (docs/architektura-pro-agenty.md §5.1)."""
import time

from backend.canvas import opora_agent_state_map_gaps as map_gaps
from backend.canvas.opora_agent_state import AgentState
from backend.canvas.test_opora_changesets import SCOPE
from backend.canvas.test_opora_changesets import service as service  # noqa: PLC0414


def node(identifier, parent=None, **extra):
    return {"id": identifier, "parentId": parent, "kind": "node", "name": identifier, "purpose": "", "x": 0, "y": 0,
            **extra}


def graph(sections=1):
    app = node("app", site={"kind": "application", "environments": [], "journeys": [
        {"id": "j", "name": "Kurz", "steps": [{"id": "k0", "page": "b"}, {"id": "k1", "page": "a"}]},
        {"id": "gone", "name": "Bez cíle", "steps": [{"id": "k0", "page": "nav"}, {"id": "k1", "page": "smazana"}]}]})
    return {"nodes": [app, node("a", "app", site={"kind": "page", "path": "/a", "goal": "g",
                                                  "sections": [{"id": f"s{i}"} for i in range(sections)]}),
                      node("b", "app", site={"kind": "page", "path": "/b"}), node("c", "a"), node("d", "a")],
            "edges": [{"id": "e1", "source": "c", "target": "d"}]}


def read(service, monkeypatch, data):
    monkeypatch.setattr(map_gaps, "architecture_graph", lambda canvas, project: data)
    return AgentState(service, clock=time.time).read(**SCOPE)


def test_map_gaps_carry_the_solving_card_and_owner_in_map_check_order(service, monkeypatch):
    document = read(service, monkeypatch, graph())
    assert document["mapGaps"] == [
        {"rule": "journey.broken", "message": "Cesta Bez cíle: chybí stránka smazana v kroku k1.", "nodeId": "app",
         "journeyId": "gone", "owner": "human"},
        {"rule": "journey.unrealized", "message": "Cesta Kurz: z /b na /a nevede vazba "
                                                  "(navigation, command, data ani sekce stránky).",
         "nodeId": "b", "journeyId": "j", "owner": "agent"},
        {"rule": "journey.unverified", "message": "Cesta Kurz: chybí ověření (doklad přehrání cesty).", "nodeId": "app",
         "journeyId": "j", "owner": "agent"},
        {"rule": "page.no-goal", "message": "Stránka nemá cíl (goal).", "nodeId": "b", "owner": "human"},
        {"rule": "section.unrealized", "message": "Sekce s0 nemá žádnou komponentu.", "nodeId": "a", "owner": "agent"},
        {"rule": "edge.carries-unset", "message": "Vazba neříká, co nese (carries).", "nodeId": "c", "edgeId": "e1",
         "owner": "agent"}]
    assert document["mapGapsTotal"] == 6


def test_map_gaps_stop_at_fifty_and_report_the_total(service, monkeypatch):
    document = read(service, monkeypatch, graph(sections=60))
    assert len(document["mapGaps"]) == map_gaps.LIMIT == 50 and document["mapGapsTotal"] == 65


def test_map_check_runs_once_per_agent_state(service, monkeypatch):
    calls = []
    original = map_gaps.check_map
    monkeypatch.setattr(map_gaps, "check_map", lambda *args, **kwargs: calls.append(1) or original(*args, **kwargs))
    read(service, monkeypatch, graph())
    assert calls == [1]
