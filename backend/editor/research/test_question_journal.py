"""Real app persistence, retry and create-only reconciliation of conversation events."""
import json
import sqlite3

import pytest

from backend.agi_pletor import questions
from backend.api.editor.test_brief_vault_routes import client_with_sector
from backend.api.editor.test_research_routes import card, post
from backend.brain_opora.determinism import brain_files
from backend.editor.node.test_removals import SCOPE
from backend.editor.research import question_journal, service as research


def test_conversation_full_events_and_heart_edits_survive_reconciliation(tmp_path):
    with client_with_sector(tmp_path) as client:
        canvas = client.app.state.service
        question, _ = questions.ask(canvas, "draft", "draft", "Login or external identity?", "t1")
        qid = question["id"]
        questions.ask(canvas, "draft", "draft", "Also cover logout", "t2")
        questions.answer(canvas, "draft", qid, "A" * 8000, ["vf_source", "vf_source"], True,
                         "Missing provider documentation", "agent:heart", "t3")
        questions.close(canvas, "draft", "Discuss later; no plan approval.", "t4")
        listing = client.get("/api/research", params=SCOPE).json()
        assert len(listing["cards"]) == 4 and len(listing["edges"]) == 3
        assert {c["title"] for c in listing["cards"]} == {
            "Otázka Pletora", "Upřesnění otázky", "Odpověď srdce", "Uzavření otázky"}
        assert all(c["topicPath"][0] == "Nezařazené otázky" for c in listing["cards"])
        assert all(c["verification"]["status"] == "unverified" for c in listing["cards"])
        assert all(c["refs"]["questionIds"] == [qid] for c in listing["cards"])
        aid = question_journal.identity(qid, "answer")
        answer = research.detail(canvas, "draft", "draft", aid)["card"]
        record = json.loads(answer["content"])["record"]
        assert record["text"] == "A" * 8000 and record["reason"] == "Missing provider documentation"
        assert record["refs"] == ["vf_source", "vf_source"] and answer["refs"]["fragmentIds"] == ["vf_source"]
        root = question_journal.identity(qid, "question")
        custom = card(root, expectedRevision=1, topicPath=["Login", "Identity"], content="Heart analysis")
        assert post(client, [custom], "retag").status_code == 200
        research.listing(canvas, "draft", "draft")
        unchanged = research.detail(canvas, "draft", "draft", root)
        assert unchanged["card"]["content"] == "Heart analysis" and len(unchanged["history"]) == 2
        assert post(client, [{"op": "archive", "entity": "card", "id": root,
                             "expectedRevision": 2, "archived": True}], "archive-q").status_code == 200
        assert len(research.listing(canvas, "draft", "draft")["cards"]) == 3
        assert research.detail(canvas, "draft", "draft", root)["card"]["archived"]


def test_projection_retries_source_after_sql_failure_and_links_future_research(tmp_path, monkeypatch):
    with client_with_sector(tmp_path) as client:
        canvas = client.app.state.service
        question, _ = questions.ask(canvas, "draft", "draft", "Question", "t1")
        real_apply = research.apply
        def fail(*args, **kwargs):
            raise sqlite3.OperationalError("temporary failure")
        with monkeypatch.context() as patch:
            patch.setattr(research, "apply", fail)
            with pytest.raises(sqlite3.OperationalError):
                research.listing(canvas, "draft", "draft")
        assert questions.listing(canvas, "draft")[0]["text"] == "Question"
        assert len(research.listing(canvas, "draft", "draft")["cards"]) == 1
        assert research.apply is real_apply
        item = card("rc_evidence")
        item["refs"]["questionIds"] = [question["id"]]
        assert post(client, [item], "evidence").status_code == 200
        linked = research.listing(canvas, "draft", "draft")
        assert len(linked["edges"]) == 1
        root = question_journal.identity(question["id"], "question")
        assert linked["edges"][0]["toId"] == root
        assert len(research.listing(canvas, "draft", "draft")["edges"]) == 1


def test_question_workspace_pin_does_not_follow_later_active_workspace(tmp_path):
    with client_with_sector(tmp_path) as client:
        canvas = client.app.state.service
        brain = brain_files.brain_dir(canvas, "draft")
        brain.mkdir(parents=True, exist_ok=True)
        active = brain / brain_files.ACTIVE
        active.write_text(json.dumps({"workspace": "draft"}), encoding="utf-8")
        question, _ = questions.ask(canvas, "draft", "main", "Pinned", "t1")
        assert question["workspace"] == "main" and question["researchWorkspace"] == "draft"
        active.write_text(json.dumps({"workspace": "another"}), encoding="utf-8")
        assert len(research.listing(canvas, "draft", "draft")["cards"]) == 1
        question_journal.reconcile(canvas, "draft", "another")  # no question moved into this scope
        with canvas.reading("draft"):
            assert not research._latest(canvas.db_for("draft"), "draft", "another", "card")


def test_precise_event_chronology_connects_answer_refinement_and_close(tmp_path):
    with client_with_sector(tmp_path) as client:
        canvas = client.app.state.service
        question, _ = questions.ask(canvas, "draft", "draft", "Login", "2026-11-08T10:00:00Z")
        qid = question["id"]
        questions.answer(canvas, "draft", qid, "First response", [], False, None,
                         "agent:heart", "2026-11-08T10:01:00Z")
        questions.ask(canvas, "draft", "draft", "Add logout", "2026-11-08T10:02:00Z")
        questions.answer(canvas, "draft", qid, "Updated response", [], False, None,
                         "agent:heart", "2026-11-08T10:03:00Z")
        questions.close(canvas, "draft", "Close the discussion", "2026-11-08T10:04:00Z")
        graph = research.listing(canvas, "draft", "draft")
        chronology = [e for e in graph["edges"] if "podle časových údajů" in e["reason"]]
        expected = [question_journal.identity(qid, kind, index) for kind, index in
                    [("question", 0), ("answer", 0), ("refinement", 0), ("answer", 1), ("close", 0)]]
        assert {(e["fromId"], e["toId"]) for e in chronology} == set(zip(expected, expected[1:]))
        source = questions.listing(canvas, "draft")[0]
        source["closedAt"] = source["answers"][-1]["at"]
        assert question_journal._chronology(source) == []  # equal timestamps are ambiguous
        source["closedAt"] = "unknown"
        assert question_journal._chronology(source) == []
