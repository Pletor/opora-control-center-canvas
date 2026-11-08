"""Synthetic integration: accepted research -> native task -> Office feedback -> same session.

No LLM or remote source is called: fixture evidence is explicitly synthetic.
"""
import json

from backend.api.brain_opora.test_gate_routes import open_session, worker
from backend.api.editor.test_brief_vault_routes import client_with_sector
from backend.api.editor.test_research_routes import card, post
from backend.api.editor.test_research_ticket_flow import gate
from backend.brain_opora.determinism import tokens
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.opora_graph_changes import OporaGraphChanges
from backend.canvas.test_opora_graph_proposals import accept
from backend.canvas.test_opora_graph_changes import change, approve
from backend.editor.node.test_removals import HEADERS, SCOPE
from backend.editor.research.test_decision_tasks import setup, TASKS


def test_accepted_research_task_ticket_roundtrip_and_archival_preserve_origin(tmp_path):
    with client_with_sector(tmp_path) as client:
        service = client.app.state.service
        review_payload = setup(service)
        _, token = tokens.issue_heart(service, "draft", "draft")
        heart = {**HEADERS, "X-Opora-Actor": "agent; name=heart", tokens.HEADER: token}
        base = "/api/research/decision-reviews"
        reviewed = client.post(base, headers=HEADERS, json={**SCOPE, "review": review_payload})
        assert reviewed.status_code == 200, reviewed.text
        review = reviewed.json()
        task_url = base + "/" + review["id"] + "/tasks"
        proposed = client.post(task_url, headers=heart, json={**SCOPE, "tasks": TASKS})
        assert proposed.status_code == 200, proposed.text
        receipt = proposed.json()
        assert receipt["accepted"] is False
        graphs = OporaGraphProposals(service)
        proposal = graphs.read("draft", "draft", receipt["proposalId"])
        accepted = accept(graphs, proposal)  # Explicit human native acceptance, separate from research review.
        reconciled = client.post(base + "/" + review["id"] + "/reconcile", headers=heart, json=SCOPE)
        assert reconciled.status_code == 200, reconciled.text
        assert reconciled.json()["acceptedRevision"] == accepted["id"]
        node_id = receipt["nodeIds"]["login"]
        document = next(item for item in accepted["documents"] if item["nodeId"] == node_id)
        assert review["id"] in document["fields"]["goal"]
        assert review["problem"]["id"] == "rc_problem" and review["evidence"][0]["id"] == "rc_fact"
        assert document["fields"]["acceptance"] == TASKS[0]["acceptance"]

        origin_session = open_session(client)
        other_session = open_session(client, {**SCOPE, "worker": {"name": "another-worker"}})
        origin, other = worker(origin_session["token"]), worker(other_session["token"])
        issued = gate(client, heart, "ticket.issue", {
            "cardId": node_id, "cardVersion": document["revision"],
            "body": {"essence": TASKS[0]["title"], "build": document["fields"]["goal"],
                     "doneCriteria": [document["fields"]["acceptance"]]}})["ticket"]
        ticket_id = issued["ticketId"]
        gate(client, origin, "ticket.claim", {"ticketId": ticket_id})
        feedback = gate(client, origin, "ticket.feedback", {"ticketId": ticket_id, "kind": "question",
                        "text": "Synthetic Office problem: tenant switching leaves a previous tenant session active."})
        feedback_id = feedback["feedback"]["feedbackId"]
        scope = {**SCOPE, "ticketId": ticket_id, "feedbackId": feedback_id}
        branch = client.post("/api/research/tickets/branch", headers=heart, json=scope)
        assert branch.status_code == 200, branch.text
        branch_data = branch.json()
        assert branch_data["origin"]["cardId"] == node_id
        assert branch_data["origin"]["cardVersion"] == document["revision"]
        assert branch_data["origin"]["sessionId"] == origin_session["sessionId"]
        assert client.post("/api/research/tickets/branch", headers=heart, json=scope).json() == branch_data

        solution = card("rc_ticket_solution", kind="decision", content="Synthetic verified test design: clear tenant-bound session before switching.")
        solution["refs"].update(nodeIds=[node_id], ticketIds=[ticket_id], sessionIds=[origin_session["sessionId"]])
        relation = {"op": "edge", "id": "re_ticket_solution", "expectedRevision": 0,
                    "fromId": solution["id"], "toId": branch_data["card"]["id"], "relation": "resolves",
                    "reason": "The design explicitly isolates the returned tenant-session problem.",
                    "resolved": "Documented session clearing behavior.", "missing": "Implementation and acceptance remain separate.",
                    "evidenceIds": ["rc_fact"]}
        saved = post(client, [solution, relation], "ticket-resolution", headers=heart)
        assert saved.status_code == 200, saved.text
        answer = {**scope, "cardId": solution["id"], "revision": 1,
                  "text": "Use the proposed tenant-bound session clearing design; obtain native plan approval for changes."}
        returned = client.post("/api/research/tickets/answer", headers=heart, json=answer)
        assert returned.status_code == 200, returned.text
        assert returned.json()["sessionId"] == origin_session["sessionId"]
        replay = client.post("/api/research/tickets/answer", headers=heart, json=answer)
        assert replay.status_code == 200 and replay.json()["replayed"]
        held = gate(client, origin, "ticket.request")["ticket"]
        assert held["ticketId"] == ticket_id and held["status"] == "in_progress"
        answer_text = held["feedback"][0]["answer"]["text"]
        origin_record = json.loads(answer_text.split("\n\n")[-1])["researchAnswer"]["origin"]
        assert origin_record["feedbackId"] == feedback_id
        assert origin_record["cardVersion"] == document["revision"]
        assert gate(client, other, "ticket.request")["ticket"] is None

        # Remove the realized task using the real reviewed graph path, then prove retained knowledge.
        gate(client, heart, "ticket.cancel", {"ticketId": ticket_id})
        edits = OporaGraphChanges(service)
        approve(edits, change(edits, {"removeNodes": [node_id]}))
        assert node_id not in {node["id"] for node in service.view("draft", "draft")["graph"]["nodes"]}
        assert client.get(base + "/" + review["id"], params=SCOPE).json() == review
        original = client.get("/api/research/cards/rc_problem", params={**SCOPE, "revision": 1})
        assert original.status_code == 200 and original.json()["card"]["revision"] == 1
        preserved = client.get("/api/research/cards/" + branch_data["card"]["id"], params=SCOPE)
        assert preserved.status_code == 200
        assert json.loads(preserved.json()["card"]["content"])["ticketOrigin"] == branch_data["origin"]
        assert client.post("/api/research/tickets/answer", headers=heart, json=answer).json()["replayed"]
