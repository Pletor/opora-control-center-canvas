"""Brána: relace, lístky s obsluhami, odpověď člověka, schránka, long-poll a události `gate.ticket`."""
import json

import pytest

from backend.brain_opora.determinism import gate, kinds
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.canvas_service import CanvasService

WORKER = {"project": "draft", "workspace": "draft", "worker": {"name": "dev"}}


@pytest.fixture
def service(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    yield canvas
    canvas.close()


def worker_session(service):
    issued = gate.open_session(service, WORKER)
    return gate.authenticate(service, issued["token"])


def events(service):
    rows = service.db_for("draft").execute(
        "SELECT actor_kind, data FROM opora_events WHERE kind='gate.ticket' ORDER BY id").fetchall()
    return [(row[0], json.loads(row[1])) for row in rows]


def test_open_session_checks_project_and_workspace(service):
    for payload, code in (({**WORKER, "project": "nikde"}, "project_not_found"),
                          ({**WORKER, "workspace": "w-unknown"}, "workspace_not_found")):
        with pytest.raises(GateError) as caught:
            gate.open_session(service, payload)
        assert caught.value.status == 404 and caught.value.code == code


def test_authenticate_refuses_invalid_token_and_other_project(service):
    issued = gate.open_session(service, WORKER)
    for token, project, status in ((None, None, 401), ("x" * 43, None, 401), (issued["token"], "jiny", 403)):
        with pytest.raises(GateError) as caught:
            gate.authenticate(service, token, project)
        assert caught.value.status == status
    with pytest.raises(GateError) as caught:
        gate.authenticate(service, issued["token"], roles=("heart",))
    assert caught.value.code == "gate_scope"


def test_next_answers_at_once_from_the_queue_and_a_refused_report_makes_no_ticket(service):
    session = worker_session(service)
    ticket = kinds.run(service, session, {"kind": "next", "body": {}})
    assert ticket["status"] == "answered" and ticket["answer"]["task"] is None and "plan" in ticket["answer"]
    assert ticket["answeredBy"] == "gate"
    with pytest.raises(GateError) as caught:
        kinds.run(service, session, {"kind": "report", "body": {}})
    assert caught.value.status == 422
    assert [data["status"] for _, data in events(service)] == ["queued", "answered"]


def test_heart_escalation_is_a_queued_ask_marked_as_from_the_heart(service):
    _, token = gate.tokens.issue_heart(service, "draft", "draft")
    heart = gate.authenticate(service, token, roles=("heart",))
    ticket = gate.escalate(service, heart, "Rozhodněte prosím.")
    assert (ticket["kind"], ticket["status"], ticket["body"]) == ("ask", "queued", {"text": "Rozhodněte prosím.",
                                                                                     "for": "human"})
    assert events(service)[-1] == ("agent", {"ticketId": ticket["ticketId"], "kind": "ask", "status": "queued",
                                             "from": "heart"})


def test_ask_waits_for_a_human_and_then_reaches_the_inbox(service):
    session = worker_session(service)
    ticket = kinds.run(service, session, {"kind": "ask", "body": {"question": "Smím?"}})
    assert ticket["status"] == "queued" and gate.inbox(service, session, 0) == {"tickets": [], "last": 0}
    answered = gate.answer(service, "draft", ticket["ticketId"], {"answer": "Ano"})
    assert answered["status"] == "answered" and answered["answeredBy"] == "human"
    with pytest.raises(GateError) as caught:
        gate.answer(service, "draft", ticket["ticketId"], {"answer": "Ne"})
    assert caught.value.code == "ticket_answered"
    box = gate.inbox(service, session, 0)
    assert [t["ticketId"] for t in box["tickets"]] == [ticket["ticketId"]] and box["last"] == box["tickets"][0]["answeredSeq"]
    assert gate.inbox(service, session, box["last"])["tickets"] == []
    expected = {"ticketId": ticket["ticketId"], "kind": "ask"}
    assert events(service) == [("agent", {**expected, "status": "queued", "from": "worker"}),
                               ("human", {**expected, "status": "answered"})]


def test_worker_reads_only_own_tickets(service):
    mine, other = worker_session(service), worker_session(service)
    ticket = kinds.run(service, mine, {"kind": "ask", "body": {"question": "?"}})
    assert gate.get_ticket(service, "draft", ticket["ticketId"], mine)["ticketId"] == ticket["ticketId"]
    with pytest.raises(GateError) as caught:
        gate.get_ticket(service, "draft", ticket["ticketId"], other)
    assert caught.value.code == "gate_scope"


def test_inbox_waits_until_an_answer_arrives_or_time_runs_out(service):
    session, clock = worker_session(service), {"now": 0.0}
    ticket = kinds.run(service, session, {"kind": "ask", "body": {"question": "?"}})
    kinds.run(service, session, {"kind": "next"})  # zodpovězený branou: do schránky nepatří

    def sleep(seconds):
        clock["now"] += seconds
        if clock["now"] >= 0.5 and gate.get_ticket(service, "draft", ticket["ticketId"])["status"] == "queued":
            gate.answer(service, "draft", ticket["ticketId"], {"answer": "Ano"})

    found = gate.inbox(service, session, 0, 5, clock=lambda: clock["now"], sleep=sleep)
    assert [t["ticketId"] for t in found["tickets"]] == [ticket["ticketId"]] and clock["now"] == 0.5
    clock["now"] = 0.0
    assert gate.inbox(service, session, found["last"], 1, clock=lambda: clock["now"], sleep=sleep) == {
        "tickets": [], "last": found["last"]}
    assert clock["now"] == 1.0


def test_worker_change_and_ask_record_intake_entries_but_sync_kinds_and_heart_escalations_do_not(service):
    """Vstupní brána (docs/navrhy/2026-10-30-vstupni-brana.md §6): lístek `change` / `ask` pracovníka = vstup."""
    session = worker_session(service)
    asked = kinds.run(service, session, {"kind": "ask", "body": {"question": "Jaká barva?"}})
    changed = kinds.run(service, session, {"kind": "change", "body": {"proposal": "Rozdělit kartu.", "reason": "Velká."}})
    again = kinds.run(service, session, {"kind": "change", "body": {"proposal": "rozdělit kartu", "reason": "Jinak."}})
    kinds.run(service, session, {"kind": "next", "body": {}})
    _, token = gate.tokens.issue_heart(service, "draft", "draft")
    gate.escalate(service, gate.authenticate(service, token, roles=("heart",)), "Rozhodněte prosím.")
    rows = service.db_for("draft").execute(
        "SELECT source, source_ref, text, verdict FROM intake_entries ORDER BY created_at, rowid").fetchall()
    assert [tuple(row) for row in rows] == [("gate_ask", asked["ticketId"], "Jaká barva?", "pending"),
                                            ("gate_change", changed["ticketId"], "Rozdělit kartu.", "pending"),
                                            ("gate_change", again["ticketId"], "rozdělit kartu", "duplicate")]
    assert again["status"] == "queued"  # duplicita lístek nezastaví, srdce se budí dál
