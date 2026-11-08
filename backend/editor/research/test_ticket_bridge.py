"""The production bridge opens one branch and replies through the existing holder poll."""
import json

from backend.api.brain_opora.test_gate_routes import open_session, worker
from backend.api.editor.test_brief_vault_routes import client_with_sector
from backend.api.editor.test_research_routes import card, post
from backend.api.editor.test_research_ticket_flow import gate
from backend.brain_opora.determinism import tokens
from backend.editor.node.test_removals import HEADERS, SCOPE, install_graph, node


def setup(client):
    install_graph(client, {"nodes": [node("s1", kind="sector"), node("login_task", parent="s1")], "edges": []})
    session = open_session(client)
    auth = worker(session["token"])
    _, token = tokens.issue_heart(client.app.state.service, "draft", "draft")
    heart = {**HEADERS, "X-Opora-Actor": "agent; name=heart", tokens.HEADER: token}
    issued = gate(client, heart, "ticket.issue", {"cardId": "login_task", "cardVersion": 3,
        "body": {"essence": "Session", "build": "Define expiration", "doneCriteria": ["Proven"]}})["ticket"]
    tid = issued["ticketId"]
    gate(client, auth, "ticket.claim", {"ticketId": tid})
    feedback = gate(client, auth, "ticket.feedback", {"ticketId": tid, "kind": "question", "text": "Expiry conflict"})
    payload = {**SCOPE, "ticketId": tid, "feedbackId": feedback["feedback"]["feedbackId"]}
    return heart, auth, session, payload


def test_branch_and_answer_real_holder_flow(tmp_path):
    with client_with_sector(tmp_path) as client:
        heart, worker_auth, session, payload = setup(client)
        before = client.get("/api/view", params=SCOPE).json()["graph"]
        branch = client.post("/api/research/tickets/branch", headers=heart, json=payload)
        assert branch.status_code == 200, branch.text
        assert client.post("/api/research/tickets/branch", headers=heart, json=payload).json() == branch.json()
        data = branch.json()
        assert data["origin"]["sessionId"] == session["sessionId"]
        assert data["origin"]["cardVersion"] == 3
        assert json.loads(data["card"]["content"])["ticketOrigin"] == data["origin"]
        answer_card = card("rc_remedy", kind="decision", content="Respect provider expiry")
        edge = {"op": "edge", "id": "re_remedy", "expectedRevision": 0, "fromId": "rc_remedy",
                "toId": data["card"]["id"], "relation": "resolves", "reason": "Resolves provider mismatch",
                "resolved": "Expiry determined", "missing": "Plan approval", "evidenceIds": []}
        assert post(client, [answer_card, edge], headers=heart).status_code == 200
        reply = {**payload, "cardId": "rc_remedy", "revision": 1, "text": "Use provider expiry; plan approval remains separate."}
        answered = client.post("/api/research/tickets/answer", headers=heart, json=reply)
        assert answered.status_code == 200, answered.text
        assert answered.json()["sessionId"] == session["sessionId"]
        assert client.post("/api/research/tickets/answer", headers=heart, json=reply).json()["replayed"]
        assert client.post("/api/research/tickets/answer", headers=heart, json={**reply, "text": "Changed"}).status_code == 409
        held = gate(client, worker_auth, "ticket.request")["ticket"]
        assert held["status"] == "in_progress"
        assert '"revision": 1' in held["feedback"][0]["answer"]["text"]
        other = worker(open_session(client, {**SCOPE, "worker": {"name": "other"}})["token"])
        assert gate(client, other, "ticket.request")["ticket"] is None
        assert client.get("/api/view", params=SCOPE).json()["graph"] == before
        assert post(client, [card("rc_remedy", expectedRevision=1, content="Later revision")], "later", headers=heart).status_code == 200
        assert client.post("/api/research/tickets/answer", headers=heart, json=reply).json()["replayed"]
        assert client.post("/api/research/tickets/answer", headers=heart, json={**reply, "revision": 2}).status_code == 409
        assert post(client, [{"op": "archive", "entity": "edge", "id": "re_remedy",
                              "expectedRevision": 1, "archived": True}], "archive-relation", headers=heart).status_code == 200
        assert client.post("/api/research/tickets/answer", headers=heart, json=reply).json()["replayed"]
        params = {**SCOPE, "kind": "node", "target": "login_task"}
        preview = client.get("/api/removal-preview", params=params).json()
        removed = client.post("/api/remove", headers=HEADERS,
                              json={**params, "digest": preview["digest"], "confirmed": True})
        assert removed.status_code == 200, removed.text
        assert client.post("/api/research/tickets/branch", headers=heart, json=payload).json() == data
        original = client.get(f'/api/research/cards/{data["card"]["id"]}', params=SCOPE).json()["card"]
        assert original["content"] == data["card"]["content"]


def test_scope_identity_and_answer_guards(tmp_path):
    with client_with_sector(tmp_path) as client:
        heart, worker_auth, _, payload = setup(client)
        url = "/api/research/tickets/branch"
        assert client.post(url, headers=worker_auth, json=payload).status_code == 403
        assert client.post(url, headers=heart, json={**payload, "project": "foreign"}).status_code == 403
        assert client.post(url, headers=HEADERS, json={**payload, "workspace": "main"}).status_code == 403
        assert client.post(url, headers=heart, json={**payload, "feedbackId": "tf_missing"}).status_code == 404
        assert client.post(url, headers=heart, json={**payload, "ticketId": "tk_missing"}).status_code == 404
        assert client.post(url, headers=heart, json=payload).status_code == 200
        assert post(client, [card("rc_unrelated")], headers=heart).status_code == 200
        reply = {**payload, "cardId": "rc_unrelated", "revision": 1, "text": "Wrong branch"}
        assert client.post("/api/research/tickets/answer", headers=heart, json=reply).status_code == 409
        assert client.post("/api/research/tickets/answer", headers=heart, json={**reply, "revision": None}).status_code == 422
        other_ticket = gate(client, heart, "ticket.issue", {"cardId": "login_task", "body": {
            "essence": "Other", "build": "Other", "doneCriteria": ["Other"]}})["ticket"]["ticketId"]
        assert client.post(url, headers=heart, json={**payload, "ticketId": other_ticket}).status_code == 404


def test_reject_foreign_origin_session_and_execution(tmp_path):
    with client_with_sector(tmp_path) as client:
        heart, _, session, payload = setup(client)
        service = client.app.state.service
        with service.lock_for("draft"), service.db_for("draft") as db:
            db.execute("UPDATE gate_sessions SET workspace_id='foreign' WHERE id=?", (session["sessionId"],))
        response = client.post("/api/research/tickets/branch", headers=heart, json=payload)
        assert response.status_code == 409
        with service.lock_for("draft"), service.db_for("draft") as db:
            db.execute("UPDATE gate_sessions SET workspace_id='draft' WHERE id=?", (session["sessionId"],))
            db.execute("UPDATE tickets SET execution_id='ex_missing' WHERE id=?", (payload["ticketId"],))
        response = client.post("/api/research/tickets/branch", headers=heart, json=payload)
        assert response.status_code == 409
        assert client.get("/api/research", params=SCOPE).json()["cards"] == []
