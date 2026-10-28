"""Brána: relace, lístky s obsluhami, odpověď člověka, schránka, long-poll a události `gate.ticket`."""
import asyncio
import json

import pytest

from backend.brain_opora.determinism import gate
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
    ticket = gate.create_request(service, session, {"kind": "next", "body": {}})
    assert ticket["status"] == "answered" and ticket["answer"]["task"] is None and "plan" in ticket["answer"]
    assert ticket["answeredBy"] == "gate"
    with pytest.raises(GateError) as caught:
        gate.create_request(service, session, {"kind": "report", "body": {}})
    assert caught.value.status == 422
    assert [data["status"] for _, data in events(service)] == ["queued", "answered"]


def test_registered_handler_gets_service_session_body_and_time(service, monkeypatch):
    session, seen = worker_session(service), []
    monkeypatch.setitem(gate.HANDLERS, "change", lambda *args: seen.append(args) or {"ok": True})
    ticket = gate.create_request(service, session, {"kind": "change", "body": {"x": 1}})
    assert ticket["answer"] == {"ok": True} and seen == [(service, session, {"x": 1}, None)]


def test_ask_waits_for_a_human_and_then_reaches_the_inbox(service):
    session = worker_session(service)
    ticket = gate.create_request(service, session, {"kind": "ask", "body": {"question": "Smím?"}})
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
    assert events(service) == [("agent", {**expected, "status": "queued"}),
                               ("human", {**expected, "status": "answered"})]


def test_worker_reads_only_own_tickets(service):
    mine, other = worker_session(service), worker_session(service)
    ticket = gate.create_request(service, mine, {"kind": "ask"})
    assert gate.get_ticket(service, "draft", ticket["ticketId"], mine)["ticketId"] == ticket["ticketId"]
    with pytest.raises(GateError) as caught:
        gate.get_ticket(service, "draft", ticket["ticketId"], other)
    assert caught.value.code == "gate_scope"


def test_long_poll_returns_when_a_ticket_arrives_or_time_runs_out():
    clock = {"now": 0.0}
    results = iter([{"tickets": []}, {"tickets": []}, {"tickets": [{"seq": 1}]}])

    async def fetch():
        return next(results)

    async def sleep(seconds):
        clock["now"] += seconds

    found = asyncio.run(gate.long_poll(fetch, 5, clock=lambda: clock["now"], sleep=sleep))
    assert found == {"tickets": [{"seq": 1}]} and clock["now"] == 0.5

    async def empty():
        return {"tickets": [], "last": 3}

    clock["now"] = 0.0
    assert asyncio.run(gate.long_poll(empty, 1, clock=lambda: clock["now"], sleep=sleep))["last"] == 3
    assert clock["now"] == 1.0
