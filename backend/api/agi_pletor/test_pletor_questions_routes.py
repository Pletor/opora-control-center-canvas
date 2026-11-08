"""Odpověď srdce na otázku Pletora přes skutečnou aplikaci: jen agent (token srdce i za zapnutou bránou), člověk 403,
404, 409, 422, opakování se nezdvojí a nová odpověď spustí výklad Pletora; seznam čte jen člověk."""
import time

from fastapi.testclient import TestClient

from backend.agi_pletor import questions
from backend.api.agi_pletor.test_linie_routes import AGENT, JSON
from backend.app.factory import create_app
from backend.brain_opora.determinism import tokens
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, seed

Q = {"project": "draft"}


def test_answer_is_agent_only_idempotent_and_wakes_pletor(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        service = client.app.state.service
        presented = []
        client.app.state.pletor.present = lambda project, workspace, question: presented.append((project, workspace))
        client.app.state.pletor.contexts[("draft", "draft")] = (0, "staré podklady")
        asked, _ = questions.ask(service, "draft", "draft", "Jak je přihlášení?", "t1")
        url = f"/api/pletor/questions/{asked['id']}/answer"
        body = {"text": "Jen e-mail.", "refs": ["vf_1"]}

        human = client.post(url, headers=JSON, params=Q, json=body)
        assert human.status_code == 403 and human.json()["code"] == "agent_only"
        assert client.post("/api/pletor/questions/pq_nic/answer", headers=AGENT, params=Q, json=body).status_code == 404
        assert client.post(url, headers=AGENT, params=Q, json={"text": " "}).status_code == 422
        assert client.post(url, headers=AGENT, params=Q, json={"text": "Nevím.", "unknown": True}).status_code == 422
        assert client.post(url, headers=AGENT, params=Q, json={**body, "refs": ["r"] * 11}).status_code == 422

        first = client.post(url, headers=AGENT, params=Q, json=body)
        assert first.status_code == 200 and first.json()["changed"] is True and first.json()["status"] == "answered"
        again = client.post(url, headers=AGENT, params=Q, json=body)
        assert again.status_code == 200 and again.json()["changed"] is False and len(again.json()["answers"]) == 1
        for _ in range(50):  # výklad běží ve vlákně
            if presented:
                break
            time.sleep(0.01)
        assert presented == [("draft", "draft")] and client.app.state.pletor.contexts == {}

        listed = client.get("/api/pletor/questions", headers=HEADERS, params=Q).json()
        assert listed["open"]["id"] == asked["id"] and len(listed["questions"]) == 1
        assert client.get("/api/pletor/questions", headers=AGENT, params=Q).status_code == 403

        questions.close(service, "draft", "Jen e-mail.", "t2")
        closed = client.post(url, headers=AGENT, params=Q, json={"text": "Jiné."})
        assert closed.status_code == 409 and closed.json()["code"] == "question_closed"


def test_heart_token_answers_through_the_gate_wall(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        service = client.app.state.service
        client.app.state.pletor.present = lambda *args: None
        assert client.post("/api/brain/gate-setting", headers=HEADERS, json={"project": "draft", "enabled": True}
                           ).status_code == 200
        asked, _ = questions.ask(service, "draft", "draft", "Jak?", "t1")
        _, token = tokens.issue_heart(service, "draft", "draft")
        heart = {**JSON, "X-Opora-Actor": "agent; name=heart", tokens.HEADER: token}
        answered = client.post(f"/api/pletor/questions/{asked['id']}/answer", headers=heart, params=Q,
                               json={"text": "Nevíme.", "unknown": True, "reason": "Chybí účet."})
        assert answered.status_code == 200 and answered.json()["answers"][0]["by"] == "agent:heart"
