"""Research persistence and authority boundaries through the real app."""
import json
from backend.api.editor.test_brief_vault_routes import client_with_sector
from backend.editor.node.test_removals import HEADERS, SCOPE
from backend.brain_opora.determinism import tokens, brain_files
from backend.editor.research.model import REFS


def card(id="rc_login", **changes):
    return {"op": "card", "id": id, "expectedRevision": 0, "kind": "finding", "title": "Login",
            "summary": "Session behavior", "topicPath": ["Login", "Logic"], "content": "Full context",
            "status": "open", "verification": {"status": "unverified", "method": "", "at": ""},
            "sources": [], "refs": {key: [] for key in REFS}, **changes}


def edge(**changes):
    return {"op": "edge", "id": "re_flow", "expectedRevision": 0, "fromId": "rc_login",
            "toId": "rc_logic", "relation": "continues_to", "reason": "UI cannot establish session behavior",
            "resolved": "UI states", "missing": "Session lifecycle", "evidenceIds": ["rc_login"], **changes}


def post(client, operations, key="batch", headers=HEADERS, **scope):
    return client.post("/api/research", headers=headers,
                       json={**SCOPE, **scope, "key": key, "operations": operations})


def test_full_detail_headers_replay_history_and_archive(tmp_path):
    with client_with_sector(tmp_path) as client:
        sources = [{"ref": f"https://example.com/{i}", "platform": "web", "quote": "q" * 3000,
                    "title": "source", "accessedAt": "2026-11-08"} for i in range(12)]
        operations = [card(content="A" * 30000, sources=sources), card("rc_logic"), edge()]
        saved = post(client, operations)
        assert saved.status_code == 200, saved.text
        assert post(client, operations).json() == saved.json()
        headers = client.get("/api/research", params=SCOPE).json()
        assert next(c for c in headers["cards"] if c["id"] == "rc_login")["sourceCount"] == 12
        assert "content" not in headers["cards"][0] and "sources" not in headers["cards"][0]
        assert headers["edges"][0]["missing"] == "Session lifecycle"
        detail = client.get("/api/research/cards/rc_login", params=SCOPE).json()
        assert detail["card"]["content"] == "A" * 30000 and detail["card"]["sources"] == sources
        assert post(client, [card(title="Changed")]).status_code == 409
        changed = post(client, [card(expectedRevision=1, title="Changed")], "change")
        assert changed.status_code == 200, changed.text
        assert post(client, [card(expectedRevision=1)], "stale").status_code == 409
        archived = post(client, [{"op": "archive", "entity": "card", "id": "rc_login",
                                  "expectedRevision": 2, "archived": True}], "archive")
        assert archived.status_code == 200
        assert len(client.get("/api/research", params=SCOPE).json()["cards"]) == 1
        assert len(client.get("/api/research", params={**SCOPE, "archived": 1}).json()["cards"]) == 2
        old = client.get("/api/research/cards/rc_login", params={**SCOPE, "revision": 1}).json()
        assert old["card"]["sources"] == sources and len(old["history"]) == 3


def test_atomic_batch_invalid_edges_and_unverified_not_facts(tmp_path):
    with client_with_sector(tmp_path) as client:
        assert post(client, [card(), edge()]).status_code == 409
        assert client.get("/api/research", params=SCOPE).json()["cards"] == []
        bad = card(verification={"status": "verified", "method": "checked", "at": "now"})
        assert post(client, [bad]).status_code == 422
        assert post(client, [card(), card("rc_logic"), edge(missing="")]).status_code == 422
        assert post(client, [card(), card("rc_logic"), edge(evidenceIds=["rc_foreign"])]).status_code == 409
        assert post(client, [card(kind=[])]).status_code == 422
        assert post(client, [card(content="X" * 2_000_001)]).status_code in (413, 422)


def test_worker_read_only_heart_write_and_workspace_scope(tmp_path):
    with client_with_sector(tmp_path) as client:
        service = client.app.state.service
        _, heart_token = tokens.issue_heart(service, "draft", "draft")
        heart = {**HEADERS, "X-Opora-Actor": "agent; name=heart", tokens.HEADER: heart_token}
        worker_session = tokens.issue_worker(service, "draft", "draft", {"name": "worker"})
        worker = {**HEADERS, "X-Opora-Actor": "agent; name=worker", tokens.HEADER: worker_session["token"]}
        assert post(client, [card()], headers=heart).status_code == 200
        assert client.get("/api/research", params=SCOPE, headers=worker).status_code == 200
        assert post(client, [card("rc_worker")], "worker", headers=worker).status_code == 403
        assert client.get("/api/research", params={**SCOPE, "workspace": "foreign"}, headers=worker).status_code == 403
        assert post(client, [card("rc_foreign")], "foreign", headers=heart, workspace="foreign").status_code == 403
        assert post(client, [card("rc_other")], "other", headers=heart, project="other").status_code == 403
        _, main_token = tokens.issue_heart(service, "draft", "main")
        main = {**heart, tokens.HEADER: main_token}
        assert post(client, [card("rc_active")], "active", headers=main).status_code == 403
        brain = brain_files.brain_dir(service, "draft")
        brain.mkdir(parents=True, exist_ok=True)
        (brain / brain_files.ACTIVE).write_text(json.dumps({"workspace": "draft"}), encoding="utf-8")
        assert post(client, [card("rc_active")], "active", headers=main).status_code == 200


def test_edge_revision_archive_and_main_workspace_resolution(tmp_path):
    with client_with_sector(tmp_path) as client:
        assert post(client, [card(), card("rc_logic"), edge()]).status_code == 200
        assert post(client, [edge(expectedRevision=1, reason="New evidence changes the next step")], "edge2").status_code == 200
        route = "/api/research/edges/re_flow"
        old = client.get(route, params={**SCOPE, "revision": 1}).json()
        assert old["edge"]["reason"] == "UI cannot establish session behavior"
        assert len(old["history"]) == 2
        assert post(client, [{"op": "archive", "entity": "edge", "id": "re_flow",
                             "expectedRevision": 2, "archived": True}], "archive-edge").status_code == 200
        assert not client.get("/api/research", params=SCOPE).json()["edges"]
        latest = client.get(route, params=SCOPE).json()
        assert latest["edge"]["archived"] and len(latest["history"]) == 3
        service = client.app.state.service
        brain = brain_files.brain_dir(service, "draft")
        brain.mkdir(parents=True, exist_ok=True)
        (brain / brain_files.ACTIVE).write_text(json.dumps({"workspace": "draft"}), encoding="utf-8")
        selected = client.get("/api/research", params={**SCOPE, "workspace": "main"})
        assert selected.status_code == 200, selected.text
        assert selected.json()["workspace"] == "draft" and len(selected.json()["cards"]) == 2
        assert client.get(route, params={**SCOPE, "workspace": "main"}).json()["workspace"] == "draft"
        saved = post(client, [card("rc_from_main")], "main-resolved", workspace="main")
        assert saved.status_code == 200 and saved.json()["workspace"] == "draft"
