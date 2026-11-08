"""Real ticket feedback -> scoped research -> answer to the original worker session."""
from backend.api.brain_opora.test_gate_routes import open_session, worker
from backend.api.editor.test_brief_vault_routes import client_with_sector
from backend.api.editor.test_research_routes import card, post
from backend.brain_opora.determinism import tokens
from backend.editor.node.test_removals import HEADERS, SCOPE, install_graph, node


def gate(client, auth, kind, body=None):
    response = client.post("/api/gate/requests", headers=auth, json={"kind": kind, "body": body or {}})
    assert response.status_code == 201, response.text
    return response.json()["answer"]


def test_worker_problem_research_and_reply_preserve_ticket_session_and_task(tmp_path):
    with client_with_sector(tmp_path) as client:
        install_graph(client, {"nodes": [node("s1", kind="sector"), node("login_task", parent="s1")], "edges": []})
        graph_before = client.get("/api/view", params=SCOPE).json()["graph"]
        origin_session = open_session(client)
        other_session = open_session(client, {**SCOPE, "worker": {"name": "other-worker"}})
        origin = worker(origin_session["token"])
        other = worker(other_session["token"])
        _, token = tokens.issue_heart(client.app.state.service, "draft", "draft")
        heart = {**HEADERS, "X-Opora-Actor": "agent; name=heart", tokens.HEADER: token}
        issued = gate(client, heart, "ticket.issue", {
            "cardId": "login_task", "body": {"essence": "Login has defined session behavior",
                                             "build": "Implement session expiration",
                                             "doneCriteria": ["Expiration behavior is covered by a test"]}})["ticket"]
        ticket_id = issued["ticketId"]
        assert issued["machine"]["cardId"] == "login_task"
        assert gate(client, origin, "ticket.claim", {"ticketId": ticket_id})["ticket"]["status"] == "claimed"
        feedback = gate(client, origin, "ticket.feedback", {
            "ticketId": ticket_id, "kind": "question", "text": "The provider lifetime differs from the proposed plan."})
        feedback_id = feedback["feedback"]["feedbackId"]
        assert feedback["ticket"]["status"] == "needs_answer"

        problem = card("rc_session_problem", kind="question", title="Session lifetime conflict",
                       content="Worker feedback " + feedback_id + ": provider lifetime differs from the plan.")
        solution = card("rc_session_remedy", kind="decision", title="Proposed session lifetime remedy",
                        status="resolved", content="Use the documented provider lifetime; the plan change remains a proposal.")
        for item in (problem, solution):
            item["refs"]["nodeIds"] = ["login_task"]
            item["refs"]["ticketIds"] = [ticket_id]
            item["refs"]["sessionIds"] = [origin_session["sessionId"]]
        edge = {"op": "edge", "id": "re_session_remedy", "expectedRevision": 0,
                "fromId": solution["id"], "toId": problem["id"], "relation": "resolves",
                "reason": "The proposed remedy answers the returned lifetime question.",
                "resolved": "A candidate implementation path is described.",
                "missing": "Plan approval is still separate.", "evidenceIds": []}
        saved = post(client, [problem, solution, edge], "ticket-research", headers=heart)
        assert saved.status_code == 200, saved.text

        # Knowledge persistence neither answers the ticket nor approves/modifies Structure.
        waiting = gate(client, origin, "ticket.request")["ticket"]
        assert waiting["status"] == "needs_answer" and waiting["feedback"][0]["answer"] is None
        assert client.get("/api/view", params=SCOPE).json()["graph"] == graph_before
        assert "approved" not in saved.json()["cards"][1]
        detail = client.get("/api/research/cards/rc_session_remedy", params=SCOPE, headers=origin)
        assert detail.status_code == 200, detail.text
        assert detail.json()["card"]["refs"] == solution["refs"]
        assert detail.json()["card"]["verification"]["status"] == "unverified"

        text = "See research card rc_session_remedy for the proposed lifetime behavior; obtain plan approval separately."
        refused = client.post("/api/gate/requests", headers=other, json={"kind": "ticket.answer", "body": {
            "ticketId": ticket_id, "feedbackId": feedback_id, "text": text}})
        assert refused.status_code == 403
        answered = gate(client, heart, "ticket.answer", {
            "ticketId": ticket_id, "feedbackId": feedback_id, "text": text})
        assert answered["ticket"]["status"] == "in_progress"

        # Existing ticket polling returns the answer to the holder, not another session.
        returned = gate(client, origin, "ticket.request")
        assert returned["held"] is True and returned["ticket"]["ticketId"] == ticket_id
        assert returned["ticket"]["feedback"][0]["feedbackId"] == feedback_id
        assert returned["ticket"]["feedback"][0]["answer"] == {"text": text}
        assert gate(client, other, "ticket.request")["ticket"] is None
        audit = client.get(f"/api/brain/tickets/{ticket_id}", params={"project": "draft"}).json()
        assert audit["sessionId"] == origin_session["sessionId"]
        assert audit["feedback"][0]["sessionId"] == origin_session["sessionId"]
        assert audit["machine"]["cardId"] == "login_task"
        assert client.get("/api/view", params=SCOPE).json()["graph"] == graph_before
