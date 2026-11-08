"""Exercise bounded reads and durable synchronization through the real app."""
import json

import pytest
from fastapi.testclient import TestClient

from backend.agi_pletor import questions
from backend.api.editor.test_brief_vault_routes import client_with_sector
from backend.api.editor.test_research_routes import card, edge, post
from backend.app.factory import create_app
from backend.brain_opora.determinism import tokens
from backend.editor.node.test_removals import HEADERS, ORIGIN, SCOPE
from backend.editor.research import events


def test_lossless_parts_pin_revision_snapshot_and_scope(tmp_path):
    with client_with_sector(tmp_path) as client:
        source = {"ref": "https://example.com", "platform": "web", "quote": "doklad " * 5000,
                  "title": "Source", "accessedAt": "2026-11-08"}
        assert post(client, [card(content="🙂 Český obsah " * 3000, sources=[source])]).status_code == 200
        route = "/api/research/cards/rc_login/parts"
        first = client.get(route, params={**SCOPE, "size": 4000}).json()
        assert first["revision"] == 1 and not first["complete"]
        assert post(client, [card(expectedRevision=1, content="new")], "new").status_code == 200
        chunks = [first["text"]]
        part = first
        while part["nextOffset"] is not None:
            part = client.get(route, params={**SCOPE, "revision": first["revision"],
                "snapshot": first["snapshot"], "offset": part["nextOffset"], "size": 4000}).json()
            chunks.append(part["text"])
        rebuilt = json.loads("".join(chunks))
        assert rebuilt["content"] == "🙂 Český obsah " * 3000 and rebuilt["sources"] == [source]
        assert client.get(route, params={**SCOPE, "offset": 1}).status_code == 422
        assert client.get(route, params={**SCOPE, "revision": 2, "snapshot": first["snapshot"]}).status_code == 409
        assert client.get(route, params={**SCOPE, "offset": -1}).status_code == 422
        assert client.get("/api/research/cards/missing/parts", params=SCOPE).status_code == 404
        session = tokens.issue_worker(client.app.state.service, "draft", "draft", {"name": "reader"})
        headers = {**HEADERS, "X-Opora-Actor": "agent; name=reader", tokens.HEADER: session["token"]}
        for path in (route, "/api/research/events", "/api/research/topics"):
            assert client.get(path, params=SCOPE, headers=headers).status_code == 200
            assert client.get(path, params={**SCOPE, "project": "foreign"}, headers=headers).status_code == 403
            assert client.get(path, params={**SCOPE, "workspace": "foreign"}, headers=headers).status_code == 403


def test_events_atomic_replay_and_question_journal(tmp_path, monkeypatch):
    with client_with_sector(tmp_path) as client:
        route = "/api/research/events"
        assert client.get(route, params=SCOPE).json()["events"] == []
        assert post(client, [card(), edge()]).status_code == 409
        assert client.get(route, params=SCOPE).json()["events"] == []
        def broken(*args, **kwargs):
            raise RuntimeError("event insert failed")
        with monkeypatch.context() as patch:
            patch.setattr(events, "record", broken)
            with pytest.raises(RuntimeError, match="event insert failed"):
                post(client, [card()], "rollback")
        assert client.get("/api/research", params=SCOPE).json()["cards"] == []
        assert post(client, [card()], "once").status_code == 200
        assert post(client, [card()], "once").status_code == 200
        first = client.get(route, params=SCOPE).json()
        assert len(first["events"]) == 1
        assert first["events"][0]["cards"] == [{"id": "rc_login", "revision": 1}]
        questions.ask(client.app.state.service, "draft", "draft", "Next question?", "now")
        added = client.get(route, params={**SCOPE, "after": first["nextCursor"]}).json()
        assert len(added["events"]) == 1 and added["events"][0]["agent"] == "question-journal"
        assert client.get(route, params={**SCOPE, "after": added["nextCursor"]}).json()["events"] == []
        page = client.get(route, params={**SCOPE, "limit": 1}).json()
        assert page["hasMore"] and page["nextCursor"] == first["nextCursor"]
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as reopened:
        persisted = reopened.get(route, params={**SCOPE, "after": first["nextCursor"]}).json()
        assert persisted == added  # reconnect replays only the remaining durable event


def test_topic_hierarchy_preserves_shared_parents_and_archive(tmp_path):
    with client_with_sector(tmp_path) as client:
        assert post(client, [card(topicPath=["Login", "UX"]),
                             card("rc_logic", topicPath=["Login", "Logic"])]).status_code == 200
        tree = client.get("/api/research/topics", params=SCOPE).json()["topics"]
        assert len(tree) == 1 and tree[0]["path"] == ["Login"] and not tree[0]["cardIds"]
        assert {child["label"]: child["cardIds"] for child in tree[0]["children"]} == {
            "UX": ["rc_login"], "Logic": ["rc_logic"]}
        assert post(client, [{"op": "archive", "entity": "card", "id": "rc_login",
                             "expectedRevision": 1, "archived": True}], "archive").status_code == 200
        assert len(client.get("/api/research/topics", params=SCOPE).json()["topics"][0]["children"]) == 1
        assert len(client.get("/api/research/topics", params={**SCOPE, "archived": True}).json()["topics"][0]["children"]) == 2
