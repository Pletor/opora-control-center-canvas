"""Outbox kind → phase/state/title of the live process (docs/zivy-proces.md §4)."""
import pytest

from backend.canvas.opora_event_process import KINDS, derive
from backend.canvas.opora_events import KINDS as OUTBOX_KINDS
from backend.canvas.process_event_validation import PHASES, STATES


def event(kind, **fields):
    base = {"id": 7, "at": "2026-10-22T10:00:00.000Z", "kind": kind, "projectId": "p1", "workspaceId": "w1",
            "nodeId": "a", "executionId": "e1", "stepId": None, "prNumber": None, "stage": None, "health": None,
            "actor": {"kind": "system", "name": "opora"}, "data": {}, "source": "opora", "phase": None,
            "state": None, "title": None, "detail": None, "refs": None, "tool": None, "externalId": None}
    return {**base, **fields}


def test_every_outbox_kind_has_a_valid_mapping():
    assert set(OUTBOX_KINDS) <= set(KINDS)
    for phase, state, title in KINDS.values():
        assert phase in PHASES and state in STATES and 0 < len(title) <= 120


@pytest.mark.parametrize(("fields", "expected"), [
    ({"kind": "lease.claimed"}, ("work", "start")),
    ({"kind": "merge.done"}, ("merge", "ok")),
    ({"kind": "card.closed"}, ("memory", "ok")),
    ({"kind": "autorebase.conflict"}, ("merge", "blocked")),
    ({"kind": "stage.changed", "stage": "review", "health": "waiting"}, ("review", "wait")),
    ({"kind": "stage.changed", "stage": "evidence", "health": "blocking"}, ("checks", "blocked")),
    ({"kind": "gate.changed", "data": {"gate": {"status": "ready"}}}, ("review", "ok")),
    ({"kind": "formal.result", "data": {"outcome": "counterexample"}}, ("checks", "fail")),
    ({"kind": "decision.created", "data": {"decision": "close_card"}}, ("merge", "wait")),
    ({"kind": "decision.resolved", "data": {"decision": "accept"}}, ("plan", "ok")),
    ({"kind": "memory.write"}, ("memory", "ok")),
])
def test_derived_phase_and_state(fields, expected):
    result = derive(event(**fields))
    assert (result["phase"], result["state"]) == expected
    assert result["schema"] == "opora.process-event/1" and result["eventId"] == "opora:7"
    assert result["refs"] == {"project": "p1", "workspace": "w1", "cardId": "a", "executionId": "e1"}


def test_stored_office_fields_win():
    stored = event("tool.use", source="office", phase="work", state="progress", title="Upravuje soubor",
                   refs={"project": "p1", "workspace": "w1"}, externalId="office:f1:3")
    result = derive(stored)
    assert (result["phase"], result["state"], result["title"]) == ("work", "progress", "Upravuje soubor")
    assert result["eventId"] == "office:f1:3" and result["refs"] == {"project": "p1", "workspace": "w1"}
