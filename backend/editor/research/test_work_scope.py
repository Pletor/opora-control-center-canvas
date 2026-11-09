"""Scoped creation attaches a reference without cloning source records."""
from backend.api.editor.test_brief_vault_routes import client_with_sector
from backend.api.editor.test_research_routes import card, post
from backend.editor.node.test_removals import SCOPE


def test_scoped_creation_replay_and_unknown_context(tmp_path):
    with client_with_sector(tmp_path) as client:
        payload = card()
        saved = post(client, [payload], scopeNodeId="s1")
        assert saved.status_code == 200, saved.text
        assert saved.json()["cards"][0]["refs"]["nodeIds"] == ["s1"]
        assert post(client, [payload], scopeNodeId="s1").json() == saved.json()
        assert payload["refs"]["nodeIds"] == []
        assert post(client, [payload], scopeNodeId="missing").status_code == 404
        assert post(client, [card("other")], key="unknown", scopeNodeId="missing").status_code == 404
        assert len(client.get("/api/research", params=SCOPE).json()["cards"]) == 1


def test_scoped_creation_keeps_shared_refs_and_rejects_malformed_refs(tmp_path):
    with client_with_sector(tmp_path) as client:
        shared = card()
        shared["refs"]["nodeIds"] = ["s1", "another-scope"]
        saved = post(client, [shared], scopeNodeId="s1")
        assert saved.status_code == 200, saved.text
        assert saved.json()["cards"][0]["refs"]["nodeIds"] == ["s1", "another-scope"]
        invalid = card("bad")
        invalid["refs"]["nodeIds"] = [{}]
        assert post(client, [invalid], key="bad", scopeNodeId="s1").status_code == 422
        assert post(client, [shared], scopeNodeId=None).status_code == 409
