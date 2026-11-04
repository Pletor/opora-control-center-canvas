"""Routy Pletora přes skutečnou aplikaci s falešným runnerem: tvar odpovědi, jen člověk, 404 a 422."""
import json

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.brain_opora.heart.process import Outcome
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed

AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=dev"}


def fake_runner(command, *, cwd, env, stdin_text, timeout, on_line=None):
    reply = {"reply": "Zapsáno.", "actions": [{"type": "vault_note", "text": "Web má dvě stránky."}]}
    result = {"type": "result", "session_id": "s1", "is_error": False, "result": json.dumps(reply, ensure_ascii=False)}
    return Outcome(0, json.dumps(result), "")


def test_message_and_state(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        client.app.state.pletor.runner, client.app.state.pletor.find = fake_runner, lambda: "claude"
        body = {**SCOPE, "text": "Rozhodli jsme: dvě stránky."}
        answer = client.post("/api/pletor/messages", headers=HEADERS, json=body)
        assert answer.status_code == 200
        assert answer.json() == {"reply": "Zapsáno.", "actions": [
            {"type": "vault_note", "text": "Web má dvě stránky.", "ok": True,
             "detail": "Zapsáno do brain/pletor_decisions.jsonl."}]}
        state = client.get("/api/pletor/state", headers=HEADERS, params=SCOPE).json()
        assert [m["role"] for m in state["messages"]] == ["human", "pletor"]
        assert state["heart"]["running"] is False and state["escalations"] == []


def test_refusals(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        assert client.post("/api/pletor/messages", headers=AGENT, json={**SCOPE, "text": "x"}).status_code == 403
        assert client.get("/api/pletor/state", headers=AGENT, params=SCOPE).status_code == 403
        missing = client.post("/api/pletor/messages", headers=HEADERS, json={**SCOPE, "project": "nikde", "text": "x"})
        assert missing.status_code == 404 and missing.json()["code"] == "project_not_found"
        assert client.post("/api/pletor/messages", headers=HEADERS, json={**SCOPE, "text": "  "}).status_code == 422
        assert client.post("/api/pletor/messages", headers=HEADERS, json={**SCOPE, "text": "x", "via": "y"}
                           ).status_code == 422
        assert client.get("/api/pletor/state", headers=HEADERS, params={"project": "draft"}).status_code == 422
