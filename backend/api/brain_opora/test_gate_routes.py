"""Brána přes skutečnou aplikaci (create_app): relace → ask čeká → odpoví člověk → schránka.

Dál: token jiného projektu je 403 `gate_scope`, neplatný nebo prošlý token 401, odpovídá jen člověk,
každá chyba nese `code` a `hint` a brána přes tunel neodpovídá.
"""
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.brain_opora.determinism import tokens

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=dev"}
SESSION = {"project": "draft", "workspace": "draft", "worker": {"name": "dev", "office": "o1"}}


def open_session(client, body=None):
    response = client.post("/api/gate/sessions", headers=AGENT, json=body or SESSION)
    assert response.status_code == 201, response.text
    return response.json()


def worker(token):
    return {**AGENT, tokens.HEADER: token}


def test_worker_asks_human_answers_and_the_answer_reaches_the_inbox(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        issued = open_session(client)
        assert set(issued) == {"sessionId", "token", "expiresAt"}
        auth = worker(issued["token"])
        asked = client.post("/api/gate/requests", headers=auth, json={"kind": "ask", "body": {"question": "Smím?"}})
        assert asked.status_code == 201 and asked.json()["status"] == "queued" and "answer" not in asked.json()
        ticket_id = asked.json()["ticketId"]
        assert client.get("/api/gate/inbox", headers=auth).json()["tickets"] == []
        # Agent odpovědět nesmí, člověk ano.
        refused = client.post(f"/api/gate/tickets/{ticket_id}/answer?project=draft", headers=AGENT, json={"answer": "x"})
        assert refused.status_code == 403 and refused.json()["code"] == "human_required" and refused.json()["hint"]
        answered = client.post(f"/api/gate/tickets/{ticket_id}/answer?project=draft", headers=HEADERS,
                               json={"answer": {"text": "Ano"}})
        assert answered.status_code == 200 and answered.json()["status"] == "answered"
        box = client.get("/api/gate/inbox", headers=auth, params={"after": 0, "wait": 1}).json()
        assert [t["ticketId"] for t in box["tickets"]] == [ticket_id] and box["tickets"][0]["answer"] == {"text": "Ano"}
        assert client.get("/api/gate/inbox", headers=auth, params={"after": box["last"]}).json()["tickets"] == []
        assert client.get(f"/api/gate/tickets/{ticket_id}", headers=auth).json()["answeredBy"] == "human"
        assert client.get(f"/api/gate/tickets/{ticket_id}", params={"project": "draft"}).status_code == 200
        feed = client.get("/api/oporahub/events", params={"project": "draft", "workspace": "draft"})
        assert feed.status_code == 200, feed.text
        kinds = [(e["kind"], e["data"]["status"]) for e in feed.json()["events"] if e["kind"] == "gate.ticket"]
        assert kinds == [("gate.ticket", "queued"), ("gate.ticket", "answered")]


def test_next_answers_at_once_from_the_queue(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        auth = worker(open_session(client)["token"])
        nxt = client.post("/api/gate/requests", headers=auth, json={"kind": "next"})
        assert nxt.status_code == 201 and nxt.json()["answer"]["task"] is None
        bad = client.post("/api/gate/requests", headers=auth, json={"kind": "deploy"})
        assert bad.status_code == 422 and "next, ask, report, change" in bad.json()["hint"]
        big = client.post("/api/gate/requests", headers=auth, json={"kind": "ask", "body": "x" * 70_000})
        assert big.status_code == 413 and big.json()["code"] == "body_too_large"


def test_token_of_another_project_is_403_gate_scope(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        other = client.post("/api/empty-project", headers=HEADERS, json={"name": "Jiný", "confirmed": True}).json()["id"]
        auth = worker(open_session(client)["token"])
        mine = client.post("/api/gate/requests", headers=auth, json={"kind": "ask"}).json()["ticketId"]
        theirs_session = open_session(client, {**SESSION, "project": other})
        theirs = worker(theirs_session["token"])
        for response in (client.get("/api/gate/inbox", headers=auth, params={"project": other}),
                         client.post(f"/api/gate/requests?project={other}", headers=auth, json={"kind": "ask"}),
                         client.get(f"/api/gate/tickets/{mine}", headers=theirs, params={"project": "draft"})):
            assert response.status_code == 403 and response.json()["code"] == "gate_scope", response.text
            assert response.json()["hint"]
        # Lístek jiného projektu token vlastního projektu nenajde.
        assert client.get(f"/api/gate/tickets/{mine}", headers=theirs).status_code == 404


def test_missing_invalid_and_expired_tokens_are_401(tmp_path, monkeypatch):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        token = open_session(client)["token"]
        for headers in (AGENT, worker("x" * 43)):
            response = client.post("/api/gate/requests", headers=headers, json={"kind": "ask"})
            assert response.status_code == 401 and response.json()["code"] == "gate_token_invalid"
        later = datetime.now(UTC) + timedelta(hours=8, minutes=1)
        real_stamp = tokens.stamp
        monkeypatch.setattr(tokens, "stamp", lambda moment=None: real_stamp(moment or later))
        expired = client.get("/api/gate/inbox", headers=worker(token))
        assert expired.status_code == 401 and expired.json()["code"] == "gate_token_invalid"


def test_gate_is_not_reachable_through_the_tunnel(tmp_path, monkeypatch):
    monkeypatch.setenv("OPORA_PUBLIC_HOSTS", "abc.trycloudflare.com")
    monkeypatch.setenv("OPORA_ACCESS_TOKEN", "t" * 32)
    with TestClient(create_app(tmp_path), base_url="https://abc.trycloudflare.com") as client:
        response = client.post("/api/gate/sessions", headers={"origin": "https://abc.trycloudflare.com",
                                                              "authorization": "Bearer " + "t" * 32}, json=SESSION)
        assert response.status_code == 403
