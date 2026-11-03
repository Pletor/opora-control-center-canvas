"""Ticket přes bránu: srdce vydá, dělník požádá, vezme, ptá se, odevzdá; oprávnění podle tokenu a stavu."""
import pytest

from backend.brain_opora.determinism import gate, kinds, ticket, tokens
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.brain_opora.determinism.kind_schemas import SCHEMAS
from backend.brain_opora.determinism.test_kinds import conforms
from backend.canvas.canvas_service import CanvasService

WORKER = {"project": "draft", "workspace": "draft", "worker": {"name": "office-1"}}
ISSUE = SCHEMAS["ticket.issue"][2]


@pytest.fixture
def service(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    yield canvas
    canvas.close()


def worker(service, name="office-1"):
    return gate.authenticate(service, gate.open_session(service, {**WORKER, "worker": {"name": name}})["token"])


def heart(service):
    _, token = tokens.issue_heart(service, "draft", "draft")
    return gate.authenticate(service, token, roles=("heart",))


def send(service, session, kind, body=None):
    answered = kinds.run(service, session, {"kind": kind, "body": body or {}})
    assert answered["status"] == "answered" and conforms(answered["answer"], SCHEMAS[kind][1]) == [], kind
    return answered["answer"]


def refused(service, session, kind, body):
    with pytest.raises(GateError) as caught:
        kinds.run(service, session, {"kind": kind, "body": body})
    return caught.value


def test_ticket_lifecycle_with_question_and_answer(service):
    brain, office = heart(service), worker(service)
    assert send(service, office, "ticket.request") == {"ticket": None, "held": False}
    issued = send(service, brain, "ticket.issue", ISSUE)["ticket"]
    assert issued["status"] == "issued" and issued["body"]["skills"] == ["ponytail@5.3.3"]
    assert issued["machine"] == {"cardId": "hero", "executionId": None, "cardVersion": 3}
    offered = send(service, office, "ticket.request")
    assert offered["held"] is False and offered["ticket"]["ticketId"] == issued["ticketId"]
    tid = issued["ticketId"]
    assert send(service, office, "ticket.claim", {"ticketId": tid})["ticket"]["status"] == "claimed"
    idea = send(service, office, "ticket.feedback", {"ticketId": tid, "kind": "idea", "text": "Přidat video."})
    assert idea["ticket"]["status"] == "in_progress" and idea["feedback"]["feedbackId"].startswith("tf_")
    question = send(service, office, "ticket.feedback", {"ticketId": tid, "kind": "question", "text": "Smím?"})
    assert question["ticket"]["status"] == "needs_answer"
    blocked = refused(service, office, "ticket.deliver", {"ticketId": tid, "summary": "Hotovo."})
    assert blocked.status == 409 and blocked.code == "ticket_state"
    answer = send(service, brain, "ticket.answer", {"ticketId": tid, "feedbackId": question["feedback"]["feedbackId"],
                                                    "text": "Ano."})
    assert answer["ticket"]["status"] == "in_progress" and answer["feedback"]["answer"] == {"text": "Ano."}
    held = send(service, office, "ticket.request")
    assert held["held"] is True and [item["answer"] for item in held["ticket"]["feedback"]] == [None, {"text": "Ano."}]
    assert send(service, office, "ticket.deliver", {"ticketId": tid, "summary": "Hotovo.", "sha": "abc1234"}) == {
        "ticket": {"ticketId": tid, "status": "delivered"}}
    full = ticket.get(service, "draft", tid)
    assert full["delivery"]["sha"] == "abc1234" and full["sessionId"] == office["id"]
    assert [item["kind"] for item in full["feedback"]] == ["idea", "question"]
    assert [row["ticketId"] for row in ticket.list_tickets(service, "draft", "draft", "delivered")["tickets"]] == [tid]
    # Každý požadavek nechal audit v gate_tickets, schránka dělníka zůstala prázdná (odpovídá brána hned).
    audit = service.db_for("draft").execute("SELECT kind FROM gate_tickets ORDER BY seq").fetchall()
    assert [row[0] for row in audit].count("ticket.feedback") == 2 and gate.inbox(service, office, 0)["tickets"] == []


def test_only_heart_issues_and_only_the_holder_works_the_ticket(service):
    brain, office, other = heart(service), worker(service), worker(service, "office-2")
    assert refused(service, office, "ticket.issue", ISSUE).code == "heart_required"
    tid = send(service, brain, "ticket.issue", ISSUE)["ticket"]["ticketId"]
    send(service, office, "ticket.claim", {"ticketId": tid})
    again = refused(service, other, "ticket.claim", {"ticketId": tid})
    assert again.status == 409 and again.code == "ticket_state"
    assert send(service, other, "ticket.request") == {"ticket": None, "held": False}
    stranger = refused(service, other, "ticket.feedback", {"ticketId": tid, "kind": "bug", "text": "Padá."})
    assert stranger.code == "ticket_not_held"
    assert refused(service, office, "ticket.claim", {"ticketId": "tk_missing"}).status == 404


def test_answer_without_feedback_id_still_answers_a_question_ticket(service):
    brain, office = heart(service), worker(service)
    asked = kinds.run(service, office, {"kind": "ask", "body": {"question": "Smím upravit app.ts?"}})
    reply = send(service, brain, "ticket.answer", {"ticketId": asked["ticketId"], "text": "Ano."})
    assert reply["ticket"]["status"] == "answered" and reply["ticket"]["answeredBy"] == "heart"
    assert gate.inbox(service, office, 0)["tickets"][0]["answer"] == {"text": "Ano."}
    tid = send(service, brain, "ticket.issue", ISSUE)["ticket"]["ticketId"]
    missing = refused(service, brain, "ticket.answer", {"ticketId": tid, "feedbackId": "tf_x", "text": "Ano."})
    assert missing.status == 404 and missing.code == "feedback_not_found"


def test_heart_cancels_work_that_no_longer_makes_sense_but_not_a_delivered_ticket(service):
    brain, office = heart(service), worker(service)
    tid = send(service, brain, "ticket.issue", ISSUE)["ticket"]["ticketId"]
    assert refused(service, office, "ticket.cancel", {"ticketId": tid}).code == "heart_required"
    assert send(service, brain, "ticket.cancel", {"ticketId": tid}) == {"ticket": {"ticketId": tid,
                                                                                  "status": "cancelled"}}
    assert send(service, office, "ticket.request") == {"ticket": None, "held": False}
    done = send(service, brain, "ticket.issue", ISSUE)["ticket"]["ticketId"]
    send(service, office, "ticket.claim", {"ticketId": done})
    send(service, office, "ticket.deliver", {"ticketId": done, "summary": "Hotovo."})
    assert refused(service, brain, "ticket.cancel", {"ticketId": done}).code == "ticket_state"
