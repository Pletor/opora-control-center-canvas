"""Agent-state over a plan larger than the cards[] cap: actions stay whole, closed cards go last, pages."""
import copy

from backend.canvas.opora_agent_state import AgentState
from backend.canvas.opora_agent_state_cards import CARD_LIMIT
from backend.canvas.test_graph_card import node
from backend.canvas.test_opora_agent_state import no_pull_module as no_pull_module  # noqa: PLC0414
from backend.canvas.test_opora_changesets import SCOPE, baseline, legacy_save
from backend.canvas.test_opora_changesets import service as service  # noqa: PLC0414
from backend.canvas.test_opora_process_sync import route
from backend.canvas.test_project_architecture import domain, page
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.agent_memory.test_completion_evidence import evidence

FILLERS = [f"f{index:03d}" for index in range(CARD_LIMIT + 1)]
CLOSED = FILLERS[:10]


def big_plan(service):
    """101 filler cards created first, then `a`: by creation order `a` sits past the old 100-card cut."""
    current = service.view("draft", "draft")
    nodes = [node(item) for item in FILLERS] + [node("b"), domain(), page(), node("a")]
    service.save_graph("draft", "draft", {"nodes": nodes, "edges": []}, current["digest"])
    legacy_save(service, goal="Read accepted task")
    baseline(service)
    route(service)  # accepted plan steps make `a` ready
    store = DesktopV3State(service)
    current = store.read(**SCOPE)
    state = copy.deepcopy(current["state"])
    for item in CLOSED:
        closed = state["nodes"].setdefault(item, {"phase": "discover", "criteria": [], "steps": []})
        closed["done"] = {"confirmed": True, "at": "2026-10-04T12:00:00+00:00", "by": "human", "note": ""}
        closed["evidence"] = evidence()
    store.save({**SCOPE, "expectedRevision": current["revision"], "state": state}, actor="human")


def test_ready_card_past_the_old_cut_keeps_its_claim_and_closed_cards_go_last(service):
    big_plan(service)
    document = AgentState(service).read(**SCOPE)
    claims = [item for item in document["actions"] if item["verb"] == "claim"]
    assert [(item["targetId"], item["status"]) for item in claims] == [("a", "ready")]
    assert next(item for item in document["stages"] if item["id"] == "claim")["count"] == 1
    cards = document["cards"]
    total = len(FILLERS) + 4  # a, b and the domain + page sectors
    assert len(cards) == CARD_LIMIT and document["cardsTotal"] == total
    assert document["truncated"] is True and document["cardsNextOffset"] == CARD_LIMIT
    assert cards[0]["nodeId"] == "a" and cards[0]["reason"] == "cards_ready"
    assert cards[0]["nextActionId"] == claims[0]["id"]
    reasons = [item["reason"] for item in cards]
    open_count = total - len(CLOSED)
    assert "card_closed" not in reasons[:open_count] and set(reasons[open_count:]) == {"card_closed"}


def test_cards_offset_pages_the_rest_with_the_same_actions(service):
    big_plan(service)
    reader = AgentState(service)
    first, second = reader.read(**SCOPE), reader.read(**SCOPE, cards_offset=CARD_LIMIT)
    assert second["actions"] == first["actions"] and second["stages"] == first["stages"]
    assert second["cardsTotal"] == first["cardsTotal"] and second["cardsNextOffset"] is None
    assert second["truncated"] is True
    assert {item["reason"] for item in second["cards"]} == {"card_closed"}
    seen = [item["nodeId"] for item in first["cards"] + second["cards"]]
    assert len(seen) == len(set(seen)) == first["cardsTotal"]
    assert reader.read(**SCOPE, cards_offset=10_000)["cards"] == []
