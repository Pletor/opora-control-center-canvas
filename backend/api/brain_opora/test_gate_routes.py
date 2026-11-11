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


def test_ticket_request_answers_at_once_and_the_old_queue_kinds_are_unknown(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        auth = worker(open_session(client)["token"])
        asked = client.post("/api/gate/requests", headers=auth, json={"kind": "ticket.request"})
        assert asked.status_code == 201 and asked.json()["answer"] == {"ticket": None, "held": False}
        for kind in ("deploy", "next", "report", "release", "task.create"):
            bad = client.post("/api/gate/requests", headers=auth, json={"kind": kind})
            assert bad.status_code == 422 and "ask, change, state, inbox" in bad.json()["hint"]
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

        ids["ticket"] = run("ask", auth)["ticketId"]
        run("change", auth)
        assert run("ticket.answer", heart, ticketId="ticket")["answer"]["ticket"]["answeredBy"] == "heart"
        box = run("inbox", auth)["answer"]
        assert [t["ticketId"] for t in box["tickets"]] == [ids["ticket"]] and box["tickets"][0]["answer"] == {
            "text": "Ano, pokračujte."}
        escalated = run("escalate", heart)["answer"]["ticket"]
        assert (escalated["kind"], escalated["status"], escalated["body"]["for"]) == ("ask", "queued", "human")
        assert run("ticket.request", auth)["answer"] == {"ticket": None, "held": False}
        ids["work"] = run("ticket.issue", heart)["answer"]["ticket"]["ticketId"]
        assert run("state", auth)["answer"]["tickets"]["issued"] == 1
        assert run("ticket.claim", auth, ticketId="work")["answer"]["ticket"]["status"] == "claimed"
        assert run("ticket.release", auth, ticketId="work")["answer"]["ticket"]["status"] == "issued"
        assert run("ticket.claim", auth, ticketId="work")["answer"]["ticket"]["status"] == "claimed"
        assert run("ticket.feedback", auth, ticketId="work")["answer"]["ticket"]["status"] == "needs_answer"
        ids["feedback"] = run("ticket.request", auth)["answer"]["ticket"]["feedback"][0]["feedbackId"]
        answered = request(client, heart, "ticket.answer", {"ticketId": ids["work"], "feedbackId": ids["feedback"],
                                                             "text": "Ano."}).json()["answer"]
        assert conforms(answered, listed["ticket.answer"]["output"]) == [] and answered["ticket"]["status"] == "in_progress"
        assert run("ticket.direct", heart, ticketId="work")["answer"]["feedback"]["kind"] == "heart.course"
        assert run("ticket.deliver", auth, ticketId="work")["answer"]["ticket"]["status"] == "delivered"
        ids["work"] = run("ticket.issue", heart)["answer"]["ticket"]["ticketId"]
        assert run("ticket.cancel", heart, ticketId="work")["answer"]["ticket"]["status"] == "cancelled"
        assert set(ran) == set(listed)
        # Synchronní druhy nechaly lístek pro audit.
        audit = client.app.state.service.db_for("draft").execute(
            "SELECT kind, answered_by FROM gate_tickets WHERE kind='ticket.cancel'").fetchall()
        assert [tuple(row) for row in audit] == [("ticket.cancel", "gate")]


def test_kinds_listing_follows_the_role(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        auth = worker(open_session(client)["token"])
        _, token = tokens.issue_heart(client.app.state.service, "draft", "draft")

        def names(headers):
            body = client.get("/api/gate/kinds", headers=headers).json()
            return body["role"], [kind["kind"] for kind in body["kinds"]]

        worker_kinds = ["ask", "change", "state", "inbox", "ticket.request",
                        "ticket.claim", "ticket.feedback", "ticket.deliver", "ticket.release"]
        heart_kinds = ["ticket.issue", "ticket.cancel", "ticket.answer", "ticket.direct", "escalate"]
        assert names(auth) == ("worker", worker_kinds)
        assert names(AGENT) == ("worker", worker_kinds)
        assert names({**AGENT, tokens.HEADER: token}) == ("heart", worker_kinds + heart_kinds)
        assert names(HEADERS) == ("human", worker_kinds + heart_kinds)
        invalid = client.get("/api/gate/kinds", headers=worker("x" * 43))
        assert invalid.status_code == 401 and invalid.json()["code"] == "gate_token_invalid"


def test_worker_sending_a_heart_kind_gets_403_with_code_and_hint(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        auth = worker(open_session(client)["token"])
        for kind in ("ticket.issue", "ticket.cancel", "ticket.answer", "escalate"):
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
                             ("/api/brain/tickets", "get"),
                             ("/api/gate/tickets/{ticket_id}/answer", "post"), ("/api/brain/heart/escalate", "post")):
            assert spec["paths"][path][method]["responses"], (path, method)
        assert {"WorkTicket", "Ticket", "KindsOut", "Refusal"} <= set(spec["components"]["schemas"])
        assert "/api/brain/tasks" not in spec["paths"] and "Task" not in spec["components"]["schemas"]


def test_ticket_issued_by_heart_claimed_over_http_and_read_for_the_office(tmp_path):
    from backend.brain_opora.determinism.kind_schemas import SCHEMAS

    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        _, heart_token = tokens.issue_heart(client.app.state.service, "draft", "draft")
        auth = worker(open_session(client)["token"])
        denied = client.post("/api/gate/requests", headers=auth,
                             json={"kind": "ticket.issue", "body": SCHEMAS["ticket.issue"][2]})
        assert denied.status_code == 403 and denied.json()["code"] == "heart_required"
        issued = client.post("/api/gate/requests", headers={**AGENT, tokens.HEADER: heart_token},
                             json={"kind": "ticket.issue", "body": SCHEMAS["ticket.issue"][2]})
        assert issued.status_code == 201, issued.text
        ticket_id = issued.json()["answer"]["ticket"]["ticketId"]
        claimed = client.post("/api/gate/requests", headers=auth, json={"kind": "ticket.claim",
                                                                         "body": {"ticketId": ticket_id}})
        assert claimed.json()["answer"]["ticket"]["status"] == "claimed"
        listed = client.get("/api/brain/tickets", params={"project": "draft", "workspace": "draft"})
        assert [t["ticketId"] for t in listed.json()["tickets"]] == [ticket_id]
        one = client.get(f"/api/brain/tickets/{ticket_id}", params={"project": "draft"}).json()
        assert conforms(one, SCHEMAS["ticket.issue"][1]["properties"]["ticket"]) == []
        assert one["status"] == "claimed" and one["body"]["skills"] == ["ponytail@5.3.3"]
        assert client.get("/api/brain/tickets/tk_none", params={"project": "draft"}).status_code == 404
        bad = client.get("/api/brain/tickets", params={"project": "draft", "workspace": "draft", "status": "x"})
        assert bad.status_code == 422 and bad.json()["hint"]
        assert one["machine"]["department"] == "design" and one["machine"]["profile"] == "frontend"


def test_restarted_office_takes_over_the_ticket_over_http_only_when_the_old_session_is_gone(tmp_path):
    from backend.brain_opora.determinism.kind_schemas import SCHEMAS

    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        service = client.app.state.service
        _, heart_token = tokens.issue_heart(service, "draft", "draft")
        old, new = open_session(client), open_session(client)
        ticket_id = request(client, {**AGENT, tokens.HEADER: heart_token}, "ticket.issue",
                            SCHEMAS["ticket.issue"][2]).json()["answer"]["ticket"]["ticketId"]
        assert request(client, worker(old["token"]), "ticket.claim", {"ticketId": ticket_id}).status_code == 201
        refused = request(client, worker(new["token"]), "ticket.claim", {"ticketId": ticket_id})
        assert refused.status_code == 409 and refused.json()["code"] == "ticket_not_held" and refused.json()["hint"]
        db = service.db_for("draft")
        with db:
            db.execute("UPDATE gate_sessions SET expires_at='2000-01-01T00:00:00Z' WHERE id=?", (old["sessionId"],))
        taken = request(client, worker(new["token"]), "ticket.claim", {"ticketId": ticket_id})
        assert taken.status_code == 201 and taken.json()["answer"]["ticket"]["status"] == "claimed"
        assert taken.json()["answer"]["ticket"]["machine"]["department"] == "design"
        one = client.get(f"/api/brain/tickets/{ticket_id}", params={"project": "draft"}).json()
        assert one["sessionId"] == new["sessionId"]