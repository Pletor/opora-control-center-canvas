"""Real holder feedback, native research provenance, replay and interrupted-write fencing."""
from backend.api.brain_opora.test_canvas_capability_routes import SCOPE, call
from backend.api.editor.test_brief_vault_routes import client_with_sector
from backend.api.editor.test_research_routes import card, post
from backend.api.editor.test_research_ticket_flow import gate
from backend.editor.research import ticket_bridge
from backend.editor.research.test_ticket_bridge import setup

BRANCH = "research_ticket_routes.branch"
ANSWER = "research_ticket_routes.answer"


def prepare(client):
    heart, worker, session, payload = setup(client)
    data = {key: payload[key] for key in ("ticketId", "feedbackId")}
    branch = call(client, heart, BRANCH, data, "branch")
    assert branch.status_code == 200, branch.text
    answer = card("rc_remedy", kind="decision", content="Respect the provider lifetime")
    edge = {"op": "edge", "id": "re_remedy", "expectedRevision": 0, "fromId": "rc_remedy",
            "toId": branch.json()["result"]["card"]["id"], "relation": "resolves", "reason": "Explains expiry",
            "resolved": "Lifetime specified", "missing": "Implementation still pending", "evidenceIds": []}
    assert post(client, [answer, edge], headers=heart).status_code == 200
    return heart, worker, session, data, branch


def test_branch_answer_native_replay_scope_and_no_approval(tmp_path):
    with client_with_sector(tmp_path) as client:
        heart, worker, session, data, branch = prepare(client)
        graph = client.get("/api/view", params=SCOPE).json()["graph"]
        assert branch.json()["verified"] and branch.json()["acceptedHead"] is None
        assert call(client, heart, BRANCH, data, "branch").json() == branch.json()
        assert call(client, heart, BRANCH, {**data, "feedbackId": "missing"}, "branch").status_code == 409
        assert call(client, worker, BRANCH, data, "worker").status_code == 403
        assert call(client, heart, BRANCH, data, "foreign", scope={**SCOPE, "workspace": "main"}).status_code == 403
        reply = {**data, "cardId": "rc_remedy", "revision": 1, "text": "Use provider expiry."}
        answered = call(client, heart, ANSWER, reply, "answer")
        assert answered.status_code == 200, answered.text
        assert answered.json()["verified"] and answered.json()["result"]["sessionId"] == session["sessionId"]
        native = gate(client, worker, "ticket.request")["ticket"]
        assert {key: native["feedback"][0][key] for key in answered.json()["result"]["feedback"]} == answered.json()["result"]["feedback"]
        audit = client.get(f"/api/brain/tickets/{data['ticketId']}", params={"project": "draft"}).json()
        assert audit["feedback"][0]["sessionId"] == session["sessionId"]
        assert call(client, heart, ANSWER, reply, "answer").json() == answered.json()
        assert call(client, heart, ANSWER, {**reply, "text": "Changed"}, "answer").status_code == 409
        assert post(client, [card("rc_remedy", expectedRevision=1, content="Later research")], "later", headers=heart).status_code == 200
        # Completed operation replays its original response, not a second answer against refreshed source revisions.
        assert call(client, heart, ANSWER, reply, "answer").json() == answered.json()
        assert call(client, heart, ANSWER, {**reply, "revision": 2}, "answer").status_code == 409
        assert client.get("/api/view", params=SCOPE).json()["graph"] == graph


def test_answer_keeps_native_reference_and_holder_guards(tmp_path):
    with client_with_sector(tmp_path) as client:
        heart, _, _, data, _ = prepare(client)
        reply = {**data, "cardId": "rc_remedy", "revision": 1, "text": "Use expiry."}
        assert post(client, [{"op": "archive", "entity": "edge", "id": "re_remedy", "expectedRevision": 1, "archived": True}], "archive", headers=heart).status_code == 200
        assert call(client, heart, ANSWER, reply, "answer").status_code == 409
        assert post(client, [{"op": "archive", "entity": "edge", "id": "re_remedy", "expectedRevision": 2, "archived": False}], "restore", headers=heart).status_code == 200
        service = client.app.state.service
        with service.lock_for("draft"), service.db_for("draft") as db:
            db.execute("UPDATE tickets SET session_id=NULL WHERE id=?", (data["ticketId"],))
        response = call(client, heart, ANSWER, reply, "answer")
        assert response.status_code == 409 and response.json()["code"] == "research_holder_changed", response.text


def test_interrupted_branch_never_reapplies_blindly(tmp_path, monkeypatch):
    with client_with_sector(tmp_path) as client:
        heart, _, _, payload = setup(client)
        data = {key: payload[key] for key in ("ticketId", "feedbackId")}
        original = ticket_bridge.open_branch
        def interrupted(*args, **kwargs):
            original(*args, **kwargs)
            raise ValueError("Injected after native commit")
        monkeypatch.setattr(ticket_bridge, "open_branch", interrupted)
        first = call(client, heart, BRANCH, data, "interrupted")
        assert first.status_code in (409, 422), first.text
        monkeypatch.setattr(ticket_bridge, "open_branch", original)
        second = call(client, heart, BRANCH, data, "interrupted")
        assert second.status_code == 409 and second.json()["code"] == "operation_incomplete", second.text
        cards = client.get("/api/research", params=SCOPE).json()["cards"]
        assert len(cards) == 1
