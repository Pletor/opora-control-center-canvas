"""Ticket přes bránu: srdce vydá, dělník požádá, vezme, ptá se, odevzdá; oprávnění podle tokenu a stavu."""
import pytest

from backend.brain_opora.determinism import gate, kinds, ticket, tokens
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.brain_opora.determinism.kind_schemas import SCHEMAS
from backend.brain_opora.determinism.test_kinds import conforms
from backend.canvas.canvas_service import CanvasService
from database.repositories import opora_events

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
    assert issued["machine"] == {"cardId": "hero", "executionId": None, "cardVersion": 3, "department": "design",
                                 "profile": "frontend", "successors": [], "predecessors": [],
                                 "pins": []}  # Brain bez ponytailu = bez výchozího pinu
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
    again = refused(service, other, "ticket.claim", {"ticketId": tid})  # živý držitel bez téže exekuce
    assert again.status == 409 and again.code == "ticket_not_held"
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


def resumed(service):
    events, _, _ = opora_events.page(service.db_for("draft"), "draft", None, 0, 500)
    return [event["data"] for event in events if event["kind"] == "ticket.resumed"]


@pytest.mark.parametrize("gone", ["expired", "revoked", "missing"])
def test_new_session_takes_over_work_of_a_session_that_is_gone(service, gone):
    brain, office, restarted = heart(service), worker(service), worker(service, "office-1b")
    tid = send(service, brain, "ticket.issue", ISSUE)["ticket"]["ticketId"]
    send(service, office, "ticket.claim", {"ticketId": tid})
    send(service, office, "ticket.feedback", {"ticketId": tid, "kind": "idea", "text": "Přidat video."})
    # Převzetí je jen výslovné: request nové relace cizí rozpracovaný ticket nenabídne.
    assert send(service, restarted, "ticket.request") == {"ticket": None, "held": False}
    db = service.db_for("draft")
    with db:
        if gone == "expired":
            db.execute("UPDATE gate_sessions SET expires_at='2000-01-01T00:00:00Z' WHERE id=?", (office["id"],))
        elif gone == "revoked":
            db.execute("UPDATE gate_sessions SET revoked_at='2000-01-01T00:00:00Z' WHERE id=?", (office["id"],))
        else:
            db.execute("DELETE FROM gate_sessions WHERE id=?", (office["id"],))
    taken = send(service, restarted, "ticket.claim", {"ticketId": tid})["ticket"]
    assert taken["status"] == "in_progress" and taken["feedback"][0]["text"] == "Přidat video."
    assert ticket.get(service, "draft", tid)["sessionId"] == restarted["id"]
    assert resumed(service) == [{"ticketId": tid, "fromSession": office["id"], "toSession": restarted["id"]}]
    assert send(service, restarted, "ticket.request")["held"] is True
    assert send(service, restarted, "ticket.deliver", {"ticketId": tid, "summary": "Hotovo."})["ticket"][
        "status"] == "delivered"


def test_issue_adds_successors_and_predecessors_of_the_card_from_its_workspace_graph(service, monkeypatch):
    from backend.brain_opora.determinism.test_ticket_model import GRAPH
    service.save_graph("draft", "draft", GRAPH, service.view("draft", "draft")["digest"])
    brain, office = heart(service), worker(service)
    issued = send(service, brain, "ticket.issue", {**ISSUE, "cardId": "a"})["ticket"]
    assert issued["body"] == send(service, brain, "ticket.issue", ISSUE)["ticket"]["body"]  # tělo se nemění
    assert issued["machine"]["successors"] == [{"cardId": "b", "name": "B", "essence": "Proč B."},
                                               {"cardId": "c", "name": "C"}]
    assert issued["machine"]["predecessors"] == [{"cardId": "d", "name": "D"}]
    assert send(service, office, "ticket.request")["ticket"]["machine"]["successors"][1] == {"cardId": "c", "name": "C"}
    lone = send(service, brain, "ticket.issue", {**ISSUE, "cardId": "lone"})["ticket"]["machine"]
    assert (lone["successors"], lone["predecessors"]) == ([], [])
    plain = send(service, brain, "ticket.issue", {"body": ISSUE["body"]})["ticket"]["machine"]
    assert (plain["successors"], plain["predecessors"]) == ([], [])
    # Karta v jiném prostoru (git projekt): sousedy dá graf prostoru ticketu, ne prostoru tokenu srdce.
    read, view = [], service.view
    monkeypatch.setattr(gate, "workspace_known", lambda *args: True)
    monkeypatch.setattr(service, "view", lambda project, workspace: read.append(workspace) or (
        {"graph": {"nodes": GRAPH["nodes"], "edges": [{"id": "x", "source": "c", "target": "lone"}]}}
        if workspace == "w2" else view(project, workspace)))
    other = send(service, brain, "ticket.issue", {**ISSUE, "cardId": "c", "workspace": "w2"})["ticket"]
    assert read == ["w2"] and other["machine"]["successors"] == [{"cardId": "lone", "name": "LONE"}]
    assert other["machine"]["predecessors"] == []


def test_card_under_a_web_domain_carries_the_design_revision(service, monkeypatch):
    from backend.project.site_admin import store
    from backend.project.site_admin.fixture import ember
    web = {"id": "web", "name": "www.ember.cz", "parentId": None, "site": {"kind": "application", "environments": []}}
    view = service.view
    monkeypatch.setattr(service, "view", lambda project, workspace: {"graph": {
        "nodes": [web, {"id": "hero", "name": "Hero", "parentId": "web"}], "edges": []}} if workspace == "draft"
        else view(project, workspace))
    brain = heart(service)
    assert "design" not in send(service, brain, "ticket.issue", ISSUE)["ticket"]["machine"]  # bez design systému
    store.write(service, "draft", 0, ember())
    issued = send(service, brain, "ticket.issue", ISSUE)["ticket"]
    assert issued["machine"]["design"] == {"revision": 1, "export": "/api/site-admin/export?project=draft"}


def test_department_and_profile_ride_in_the_machine_layer_and_are_checked(service):
    brain, office = heart(service), worker(service)
    plain = send(service, brain, "ticket.issue", {"body": ISSUE["body"], "profile": None})["ticket"]
    assert plain["machine"]["department"] is None and plain["machine"]["profile"] is None
    tid = send(service, brain, "ticket.issue", ISSUE)["ticket"]["ticketId"]
    send(service, brain, "ticket.cancel", {"ticketId": plain["ticketId"]})
    offered = send(service, office, "ticket.request")["ticket"]
    assert offered["ticketId"] == tid and offered["machine"]["department"] == "design"
    assert offered["machine"]["profile"] == "frontend"
    for bad in ("Design", "-x", "a" * 41, "back end", 7):
        wrong = refused(service, brain, "ticket.issue", {**ISSUE, "department": bad})
        assert wrong.status == 422 and wrong.code == "invalid_payload", bad
    assert refused(service, brain, "ticket.issue", {**ISSUE, "profile": "fe_1"}).code == "invalid_payload"


def test_intent_criteria_of_the_approved_page_intent_land_in_done_criteria(service):
    from backend.flow.workflows import approve, create_draft, create_workflow, set_candidate
    graph = {"nodes": [{"id": "in", "type": "intent.entry"},
                       {"id": "ok", "type": "intent.done", "params": {"claim": "Formulář odešle e-mail.", "check": "email"}},
                       {"id": "mapa", "type": "intent.done", "params": {"claim": "Mapa ukazuje sídlo.", "check": "visible"}}],
             "edges": []}
    with service.registry_lock:
        service.db.execute("INSERT INTO projects(id,name) VALUES('draft','Draft')")  # vestavěný projekt v registru není
        wid = create_workflow(service.db, "page_intent", "Kontakt", project_id="draft", owner_ref="opora:page:kontakt")["id"]
        version = set_candidate(service.db, create_draft(service.db, wid, graph)["id"])
    brain = heart(service)
    body = {"body": ISSUE["body"], "intent": {"workflowVersionId": version["id"], "nodeIds": ["ok", "mapa"]}}
    pending = refused(service, brain, "ticket.issue", body)  # kandidát ještě není schválený
    assert pending.status == 422 and pending.code == "ticket_intent"
    with service.registry_lock:
        approve(service.db, version["id"], "human", None)
    issued = send(service, brain, "ticket.issue", body)["ticket"]
    assert issued["body"]["doneCriteria"] == [*ISSUE["body"]["doneCriteria"], "Formulář odešle e-mail.", "Mapa ukazuje sídlo."]
    assert issued["machine"]["intent"] == {"workflowVersionId": version["id"], "nodeIds": ["ok", "mapa"]}
    assert refused(service, brain, "ticket.issue", {**body, "intent": {**body["intent"], "nodeIds": ["in"]}}).code == "ticket_intent"
    assert refused(service, brain, "ticket.issue", {**body, "intent": {"workflowVersionId": "nic", "nodeIds": ["ok"]}}).code == "ticket_intent"
    for bad in ({"workflowVersionId": version["id"]}, {"workflowVersionId": version["id"], "nodeIds": []}, "ok"):
        assert refused(service, brain, "ticket.issue", {**body, "intent": bad}).code == "invalid_payload", bad
