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


def test_research_request_is_visible_pending_plan_without_second_heart_wake():
    from backend.canvas.opora_events import QUIET
    from backend.flow.catalogs.heart.inputs import wake_input
    source = event('research.planning.requested', nodeId=None, executionId=None,
                   data={'continuationId': 'rp_fixture', 'researchId': 'rc_fixture', 'researchRevision': 1})
    result = derive(source)
    assert (result['phase'], result['state']) == ('plan', 'wait')
    assert result['title'] == 'Naplánováno pokračování po rešerši'
    assert result['refs'] == {'project': 'p1', 'workspace': 'w1'}
    assert source['kind'] in QUIET  # No unrelated card-stage refresh.
    assert wake_input(source) is None  # Only durable continuation reconciliation schedules the run.
