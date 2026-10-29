"""Brána přes skutečnou aplikaci (create_app): relace → ask čeká → odpoví člověk → schránka.

Dál: token jiného projektu je 403 `gate_scope`, neplatný nebo prošlý token 401, odpovídá jen člověk,
každá chyba nese `code` a `hint` a brána přes tunel neodpovídá.
"""
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.brain_opora.determinism import tokens
from backend.brain_opora.determinism.test_kinds import conforms

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
        mine = client.post("/api/gate/requests", headers=auth, json={"kind": "ask", "body": {"question": "?"}}).json()["ticketId"]
        theirs_session = open_session(client, {**SESSION, "project": other})
        theirs = worker(theirs_session["token"])
        for response in (client.get("/api/gate/inbox", headers=auth, params={"project": other}),
                         client.post(f"/api/gate/requests?project={other}", headers=auth, json={"kind": "ask", "body": {"question": "?"}}),
                         client.get(f"/api/gate/tickets/{mine}", headers=theirs, params={"project": "draft"})):
            assert response.status_code == 403 and response.json()["code"] == "gate_scope", response.text
            assert response.json()["hint"]
        # Lístek jiného projektu token vlastního projektu nenajde.
        assert client.get(f"/api/gate/tickets/{mine}", headers=theirs).status_code == 404


def test_missing_invalid_and_expired_tokens_are_401(tmp_path, monkeypatch):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        token = open_session(client)["token"]
        for headers in (AGENT, worker("x" * 43)):
            response = client.post("/api/gate/requests", headers=headers, json={"kind": "ask", "body": {"question": "?"}})
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


def request(client, headers, kind, body):
    return client.post("/api/gate/requests", headers=headers, json={"kind": kind, "body": body})


def test_every_kind_example_runs_through_the_gate_and_answers_its_output_schema(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        auth = worker(open_session(client)["token"])
        _, token = tokens.issue_heart(client.app.state.service, "draft", "draft")
        heart = {**AGENT, tokens.HEADER: token}
        listed = {kind["kind"]: kind for kind in client.get("/api/gate/kinds", headers=heart).json()["kinds"]}
        ran, ids = [], {}

        def run(name, headers, **swap):
            kind = listed[name]
            body = kind["example"] | {key: ids[value] for key, value in swap.items()}
            response = request(client, headers, name, body)
            assert response.status_code == 201, (name, response.text)
            out = response.json()
            if kind["sync"]:
                assert out["status"] == "answered" and conforms(out["answer"], kind["output"]) == [], (name, out)
            else:
                assert out["status"] == "queued" and "answer" not in out, name
            ran.append(name)
            return out

        ids["task"] = run("task.create", heart)["answer"]["task"]["taskId"]
        assert run("state", auth)["answer"]["queue"]["ready"] == 1
        assert run("next", auth)["answer"]["task"]["id"] == ids["task"]
        assert run("release", auth, taskId="task")["answer"]["task"]["status"] == "ready"
        assert run("next", auth)["answer"]["task"]["id"] == ids["task"]
        assert run("report", auth, taskId="task")["answer"]["task"]["status"] == "done"
        ids["ticket"] = run("ask", auth, taskId="task")["ticketId"]
        run("change", auth, taskId="task")
        assert run("ticket.answer", heart, ticketId="ticket")["answer"]["ticket"]["answeredBy"] == "heart"
        box = run("inbox", auth)["answer"]
        assert [t["ticketId"] for t in box["tickets"]] == [ids["ticket"]] and box["tickets"][0]["answer"] == {
            "text": "Ano, pokračujte."}
        ids["task"] = run("task.create", heart)["answer"]["task"]["taskId"]
        assert run("task.cancel", heart, taskId="task")["answer"]["task"]["status"] == "cancelled"
        escalated = run("escalate", heart)["answer"]["ticket"]
        assert (escalated["kind"], escalated["status"], escalated["body"]["for"]) == ("ask", "queued", "human")
        assert set(ran) == set(listed)
        # Synchronní druhy nechaly lístek pro audit.
        audit = client.app.state.service.db_for("draft").execute(
            "SELECT kind, answered_by FROM gate_tickets WHERE kind='task.cancel'").fetchall()
        assert [tuple(row) for row in audit] == [("task.cancel", "gate")]


def test_kinds_listing_follows_the_role(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        auth = worker(open_session(client)["token"])
        _, token = tokens.issue_heart(client.app.state.service, "draft", "draft")

        def names(headers):
            body = client.get("/api/gate/kinds", headers=headers).json()
            return body["role"], [kind["kind"] for kind in body["kinds"]]

        worker_kinds = ["next", "ask", "report", "change", "state", "inbox", "release"]
        heart_kinds = ["task.create", "task.cancel", "ticket.answer", "escalate"]
        assert names(auth) == ("worker", worker_kinds)
        assert names(AGENT) == ("worker", worker_kinds)
        assert names({**AGENT, tokens.HEADER: token}) == ("heart", worker_kinds + heart_kinds)
        assert names(HEADERS) == ("human", worker_kinds + heart_kinds)
        invalid = client.get("/api/gate/kinds", headers=worker("x" * 43))
        assert invalid.status_code == 401 and invalid.json()["code"] == "gate_token_invalid"


def test_worker_sending_a_heart_kind_gets_403_with_code_and_hint(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        auth = worker(open_session(client)["token"])
        for kind in ("task.create", "task.cancel", "ticket.answer", "escalate"):
            refused = request(client, auth, kind, {})
            assert refused.status_code == 403 and refused.json()["code"] == "heart_required", kind
            assert refused.json()["hint"]


def test_openapi_documents_gate_and_brain_routes(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        spec = client.get("/openapi.json").json()
        requests = spec["paths"]["/api/gate/requests"]["post"]
        assert "kind" in requests["requestBody"]["content"]["application/json"]["schema"]["properties"]
        assert "201" in requests["responses"] and "403" in requests["responses"]
        for path, method in (("/api/gate/kinds", "get"), ("/api/gate/inbox", "get"), ("/api/gate/sessions", "post"),
                             ("/api/brain/tasks", "post"), ("/api/brain/tasks", "get"),
                             ("/api/gate/tickets/{ticket_id}/answer", "post"), ("/api/brain/heart/escalate", "post")):
            assert spec["paths"][path][method]["responses"], (path, method)
        assert {"Task", "Ticket", "KindsOut", "Refusal"} <= set(spec["components"]["schemas"])
