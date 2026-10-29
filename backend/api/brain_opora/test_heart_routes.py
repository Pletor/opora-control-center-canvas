"""Srdce přes skutečnou aplikaci (docs/brain-heart.md §1, §4, §5): zprávy, stav, snímek, eskalace a token srdce
v úkolech a odpovědích. Supervisor v testech neběží (OPORA_HEART=off), žádný proces `claude` nevznikne."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.brain_opora.determinism import gate, tokens
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed

AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=dev"}
SESSION = {"project": "draft", "workspace": "draft", "worker": {"name": "dev"}}
MESSAGE = {**SCOPE, "text": "Chci web o dvou stránkách."}


def code(response):
    return response.json().get("code")


def gate_on(client):
    assert client.post("/api/brain/gate-setting", headers=HEADERS, json={"project": "draft", "enabled": True}
                       ).status_code == 200


def test_messages_are_human_only_need_the_gate_and_show_in_status(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        assert client.app.state.heart.thread is None  # OPORA_HEART=off
        assert client.post("/api/brain/heart/messages", headers=AGENT, json=MESSAGE).status_code == 403
        assert code(client.post("/api/brain/heart/messages", headers=HEADERS, json=MESSAGE)) == "gate_off"
        gate_on(client)
        assert code(client.post("/api/brain/heart/messages", headers=HEADERS, json={**SCOPE, "text": " "})
                    ) == "invalid_payload"
        queued = client.post("/api/brain/heart/messages", headers=HEADERS, json=MESSAGE)
        assert queued.status_code == 200 and queued.json() == {"queued": True, "pending": 1}
        status = client.get("/api/brain/heart/status", params={"project": "draft"}).json()
        assert status["pending"] == 1 and status["batches"] == [] and status["session"]["sessionId"] is None
        assert status["enabled"] is False and status["nextAllowedAt"]
        assert client.get("/api/brain/heart/status", params={"project": "nikde"}).status_code == 404
        text = client.get("/api/brain/heart/snapshot", params=SCOPE).json()["snapshot"]
        assert text.startswith("PROJEKT") and "FRONTA ÚKOLŮ" in text


def test_heart_token_writes_tasks_answers_and_escalates_in_its_project(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        gate_on(client)
        service = client.app.state.service
        _, token = tokens.issue_heart(service, "draft", "draft")
        heart = {**HEADERS, tokens.HEADER: token}
        client.cookies.clear()  # srdce nemá doklad UI
        task = client.post("/api/brain/tasks", headers=heart, json={**SCOPE, "order": 2, "title": "Hero",
                                                                    "body": {"do": "Hero sekce"}})
        assert task.status_code == 201, task.text
        assert (task.json()["createdBy"], task.json()["order"]) == ("heart", 2)
        cancel = client.post(f"/api/brain/tasks/{task.json()['taskId']}/cancel?project=draft", headers=heart, json={})
        assert cancel.status_code == 200 and cancel.json()["status"] == "cancelled"
        worker = {**AGENT, tokens.HEADER: client.post("/api/gate/sessions", headers=AGENT, json=SESSION).json()["token"]}
        ticket = client.post("/api/gate/requests", headers=worker, json={"kind": "ask", "body": {"question": "?"}}).json()
        answered = client.post(f"/api/gate/tickets/{ticket['ticketId']}/answer?project=draft", headers=heart,
                               json={"answer": {"text": "Ano"}})
        assert answered.status_code == 200 and answered.json()["answeredBy"] == "heart", answered.text
        # Pracovník ani agent bez tokenu srdce neodpovídají a úkoly nepíší.
        ticket = client.post("/api/gate/requests", headers=worker, json={"kind": "ask", "body": {"question": "?"}}).json()
        refused = client.post(f"/api/gate/tickets/{ticket['ticketId']}/answer?project=draft", headers=worker,
                              json={"answer": "x"})
        assert refused.status_code == 403 and code(refused) == "human_required"
        assert client.post("/api/brain/tasks", headers=AGENT, json={**SCOPE, "title": "x", "body": {"do": "x"}}
                           ).status_code == 403
        escalated = client.post("/api/brain/heart/escalate", headers=heart, json={**SCOPE, "text": "Barva?"})
        assert escalated.status_code == 201 and escalated.json()["kind"] == "ask", escalated.text
        # Pracovníka zastaví už zeď (zápis mimo /api/gate/*).
        assert code(client.post("/api/brain/heart/escalate", headers=worker, json={**SCOPE, "text": "x"})
                    ) == "gate_required"
        assert client.post("/api/brain/heart/messages", headers=heart, json=MESSAGE).status_code == 403


def test_heart_of_another_project_has_no_writer_rights_here(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        gate_on(client)
        other = client.post("/api/empty-project", headers=HEADERS, json={"name": "Jiný", "confirmed": True}).json()["id"]
        _, foreign = tokens.issue_heart(client.app.state.service, other, "draft")
        response = client.post("/api/brain/tasks", headers={**AGENT, tokens.HEADER: foreign},
                               json={**SCOPE, "title": "x", "body": {"do": "x"}})
        assert response.status_code == 403 and code(response) == "gate_scope"


def test_heart_drives_the_queue_through_the_gate_in_a_gate_on_project(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        gate_on(client)
        _, token = tokens.issue_heart(client.app.state.service, "draft", "draft")
        heart = {**HEADERS, tokens.HEADER: token}
        client.cookies.clear()  # srdce nemá doklad UI

        def gate(kind, body, query=""):
            return client.post("/api/gate/requests" + query, headers=heart, json={"kind": kind, "body": body})

        created = gate("task.create", {"title": "Hero", "order": 1, "body": {"do": "Hero sekce"}})
        assert created.status_code == 201, created.text
        task = created.json()["answer"]["task"]
        assert (task["createdBy"], task["workspaceId"], task["order"]) == ("heart", "draft", 1)
        cancelled = gate("task.cancel", {"taskId": task["taskId"]}, "?project=draft")
        assert cancelled.status_code == 201 and cancelled.json()["answer"]["task"]["status"] == "cancelled"
        again = gate("task.cancel", {"taskId": task["taskId"]})
        assert again.status_code == 409 and code(again) == "task_closed" and again.json()["hint"]
        assert code(gate("ticket.answer", {"ticketId": "gt_none", "text": "x"})) == "ticket_not_found"


def test_escalations_are_for_the_human_and_an_answer_wakes_the_heart(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        gate_on(client)
        service, heart = client.app.state.service, client.app.state.heart
        _, token = tokens.issue_heart(service, "draft", "draft")
        ticket = gate.escalate(service, tokens.verify(service, token), "Jakou barvu?")
        listed = client.get("/api/brain/heart/escalations", headers=HEADERS, params=SCOPE)
        assert listed.status_code == 200, listed.text
        assert [(e["ticketId"], e["text"]) for e in listed.json()["escalations"]] == [(ticket["ticketId"], "Jakou barvu?")]
        # Agent ani srdce otázky pro člověka nečtou; chybějící prostor je 422.
        assert client.get("/api/brain/heart/escalations", headers=AGENT, params=SCOPE).status_code == 403
        assert client.get("/api/brain/heart/escalations", headers=HEADERS, params={"project": "draft"}
                          ).status_code == 422
        answered = client.post(f"/api/gate/tickets/{ticket['ticketId']}/answer?project=draft", headers=HEADERS,
                               json={"answer": {"text": "Modrou"}})
        assert answered.status_code == 200 and answered.json()["answeredBy"] == "human", answered.text
        assert [item for _, item, _ in heart.pending["draft"]] == [
            {"type": "message", "text": f"ODPOVĚĎ ČLOVĚKA na {ticket['ticketId']}: Modrou"}]
        assert client.get("/api/brain/heart/status", params={"project": "draft"}).json()["pending"] == 1
        assert client.get("/api/brain/heart/escalations", headers=HEADERS, params=SCOPE).json() == {"escalations": []}


def test_answer_to_a_worker_ticket_does_not_wake_the_heart(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        gate_on(client)
        worker = {**AGENT, tokens.HEADER: client.post("/api/gate/sessions", headers=AGENT, json=SESSION).json()["token"]}
        asked = client.post("/api/gate/requests", headers=worker,
                            json={"kind": "ask", "body": {"question": "Smím?"}})
        assert asked.status_code == 201, asked.text
        answered = client.post(f"/api/gate/tickets/{asked.json()['ticketId']}/answer?project=draft", headers=HEADERS,
                               json={"answer": {"text": "Ano"}})
        assert answered.status_code == 200, answered.text
        assert client.app.state.heart.pending.get("draft", []) == []
