"""New closures carry context; old revisions remain readable and replayable."""
import json

import pytest

from backend.agi_pletor import questions
from backend.api.editor.test_brief_vault_routes import client_with_sector
from backend.api.editor.test_research_routes import card, edge, post
from backend.editor.node.test_removals import SCOPE
from backend.editor.research import question_journal
from backend.editor.research.test_ticket_bridge import setup


def legacy_blank(client, edge_id):
    """Simulate an immutable row written before closure-context validation existed."""
    canvas = client.app.state.service
    with canvas.lock_for("draft"), canvas.db_for("draft") as db:
        row = db.execute("SELECT payload FROM research_edge_revisions WHERE id=? AND revision=1", (edge_id,)).fetchone()
        payload = {**json.loads(row[0]), "resolved": "", "missing": ""}
        db.execute("UPDATE research_edge_revisions SET payload=? WHERE id=? AND revision=1",
                   (json.dumps(payload), edge_id))
    return payload


@pytest.mark.parametrize("field", ["resolved", "missing"])
def test_new_resolution_requires_both_context_fields(tmp_path, field):
    with client_with_sector(tmp_path) as client:
        operation = edge(relation="resolves", **{field: " "})
        result = post(client, [card(), card("rc_logic"), operation])
        assert result.status_code == 422
        assert client.get("/api/research", params=SCOPE).json()["cards"] == []


def test_old_blank_resolution_can_be_read_and_archived_without_rewrite(tmp_path):
    with client_with_sector(tmp_path) as client:
        assert post(client, [card(), card("rc_logic"), edge(relation="resolves")]).status_code == 200
        original = legacy_blank(client, "re_flow")
        route = "/api/research/edges/re_flow"
        assert client.get(route, params=SCOPE).json()["edge"] == original
        assert post(client, [{"op": "archive", "entity": "edge", "id": "re_flow",
                             "expectedRevision": 1, "archived": True}], "archive").status_code == 200
        assert client.get(route, params={**SCOPE, "revision": 1}).json()["edge"] == original
        assert client.get(route, params=SCOPE).json()["edge"]["archived"]


@pytest.mark.parametrize("note", ["", "Defer the decision until provider documentation is available."])
def test_conversation_close_does_not_claim_problem_resolution(tmp_path, note):
    with client_with_sector(tmp_path) as client:
        canvas = client.app.state.service
        question, _ = questions.ask(canvas, "draft", "draft", "Provider expiry?", "t1")
        questions.close(canvas, "draft", note, "t2")
        graph = client.get("/api/research", params=SCOPE).json()
        close_id = question_journal.identity(question["id"], "close")
        closure = next(item for item in graph["edges"] if item["fromId"] == close_id)
        assert closure["relation"] == "elaborates" and note in closure["reason"]
        assert closure["resolved"] == closure["missing"] == ""
        detail = client.get("/api/research/cards/" + close_id, params=SCOPE).json()
        assert note in detail["card"]["content"]


def test_ticket_first_delivery_rejects_legacy_blank_but_completed_replay_survives(tmp_path):
    with client_with_sector(tmp_path) as client:
        heart, _, _, payload = setup(client)
        branch = client.post("/api/research/tickets/branch", headers=heart, json=payload).json()["card"]
        link = edge(id="re_solution", fromId="rc_solution", toId=branch["id"], relation="resolves",
                    evidenceIds=[], resolved="Provider expiry rule established", missing="Human acceptance of revised task")
        assert post(client, [card("rc_solution"), link], headers=heart).status_code == 200
        legacy_blank(client, "re_solution")
        reply = {**payload, "cardId": "rc_solution", "revision": 1, "text": "Use provider expiry."}
        route = "/api/research/tickets/answer"
        assert client.post(route, headers=heart, json=reply).status_code == 409
        assert post(client, [{**link, "expectedRevision": 1}], "complete-context", headers=heart).status_code == 200
        assert client.post(route, headers=heart, json=reply).status_code == 200
        # Historical replay returns the delivered answer even when the qualifying edge is archived.
        assert post(client, [{"op": "archive", "entity": "edge", "id": "re_solution",
                             "expectedRevision": 2, "archived": True}], "archive", headers=heart).status_code == 200
        assert client.post(route, headers=heart, json=reply).json()["replayed"]
