"""Čistý model ticketu: přechody hlídá `advance`, tělo pro dělníka je bez ID a s výchozím pinem ponytail."""
from itertools import pairwise

import pytest

from backend.brain_opora.determinism import kind_schemas, ticket_model
from backend.brain_opora.determinism.gate_payloads import GateError

BODY = {"essence": "Proč.", "build": "Co.", "doneCriteria": ["npm test projde"]}


def test_happy_path_and_rework_are_allowed():
    path = ["draft", "issued", "claimed", "in_progress", "needs_answer", "in_progress", "delivered", "in_progress",
            "delivered", "verified", "closed"]
    for current, target in pairwise(path):
        assert ticket_model.advance(current, target) == target


@pytest.mark.parametrize("current, target", [("issued", "delivered"), ("claimed", "needs_answer"),
                                             ("needs_answer", "delivered"), ("closed", "issued"),
                                             ("cancelled", "issued"), ("failed", "in_progress"),
                                             ("verified", "failed"), ("issued", "nonsense")])
def test_forbidden_transition_is_a_409_with_allowed_targets(current, target):
    with pytest.raises(GateError) as caught:
        ticket_model.advance(current, target)
    assert caught.value.status == 409 and caught.value.code == "ticket_state" and "Povolené" in caught.value.hint


def test_every_state_has_a_rule_and_terminal_states_lead_nowhere():
    assert set(ticket_model.TRANSITIONS) == set(ticket_model.STATES)
    assert list(ticket_model.STATES) == kind_schemas.STATES
    assert all(target in ticket_model.STATES for targets in ticket_model.TRANSITIONS.values() for target in targets)
    assert [state for state, targets in ticket_model.TRANSITIONS.items() if not targets] == ["closed", "failed",
                                                                                            "cancelled"]


def test_body_gets_default_pin_and_keeps_layers_apart():
    body, machine = ticket_model.issue_payload({"body": BODY, "cardId": "hero", "cardVersion": 2,
                                                "department": "design"})
    assert body == {**BODY, "openPaths": [], "cautions": [], "skills": ["ponytail@5.3.3"]}
    assert machine == {"cardId": "hero", "executionId": None, "cardVersion": 2, "department": "design",
                       "profile": None}


def card(node_id, purpose=""):
    return {"id": node_id, "parentId": None, "kind": "node", "name": node_id.upper(), "purpose": purpose, "x": 0, "y": 0}


GRAPH = {"nodes": [card("a"), card("b", " Proč B. "), card("c"), card("d"), card("lone")],
         "edges": [{"id": "e1", "source": "a", "target": "b"},
                   {"id": "e2", "source": "a", "target": "c", "port": "block", "sourceBlockId": "k", "sourcePortId": "p"},
                   {"id": "e3", "source": "a", "target": "b", "port": "block", "sourceBlockId": "k", "sourcePortId": "q"},
                   {"id": "e4", "source": "a", "target": "d", "port": "rule"},
                   {"id": "e5", "source": "d", "target": "a", "port": "next"}]}


def test_neighbors_follow_next_and_block_edges_of_the_card():
    assert ticket_model.neighbors(GRAPH, "a") == {
        "successors": [{"cardId": "b", "name": "B", "essence": "Proč B."}, {"cardId": "c", "name": "C"}],
        "predecessors": [{"cardId": "d", "name": "D"}]}  # vazba rule není práce, b je jen jednou
    assert ticket_model.neighbors(GRAPH, "c") == {"successors": [], "predecessors": [{"cardId": "a", "name": "A"}]}
    assert ticket_model.neighbors(GRAPH, "lone") == {"successors": [], "predecessors": []}
    assert ticket_model.neighbors(GRAPH, "nikde") == {"successors": [], "predecessors": []}


@pytest.mark.parametrize("payload", [
    {"body": {**BODY, "build": "Navaž na tk_0123456789abcdef."}},
    {"body": {**BODY, "doneCriteria": []}},
    {"body": {**BODY, "skills": ["ponytail"]}},
    {"body": {**BODY, "id": "x"}},
    {"body": BODY, "cardVersion": -1},
    {"body": BODY, "cardId": "../x"},
    {"body": BODY, "department": "Design"},
    {"body": BODY, "profile": "a" * 41},
    {"body": {"essence": "Proč."}},
])
def test_bad_issue_bodies_are_422(payload):
    with pytest.raises(GateError) as caught:
        ticket_model.issue_payload(payload)
    assert caught.value.status == 422 and caught.value.hint


def test_feedback_and_delivery_bodies():
    assert ticket_model.feedback_payload({"ticketId": "tk_1", "kind": "idea", "text": " Víc barev. "}) == (
        "tk_1", "idea", "Víc barev.")
    assert ticket_model.deliver_payload({"ticketId": "tk_1", "summary": "Hotovo.", "sha": "abc1234"}) == (
        "tk_1", {"summary": "Hotovo.", "sha": "abc1234"})
    for call, body in ((ticket_model.feedback_payload, {"ticketId": "tk_1", "kind": "wish", "text": "x"}),
                       (ticket_model.deliver_payload, {"ticketId": "tk_1", "summary": "x", "sha": "zz"})):
        with pytest.raises(GateError):
            call(body)
