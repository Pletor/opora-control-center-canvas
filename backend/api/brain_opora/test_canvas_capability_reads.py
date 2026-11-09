"""Category adapters preserve exact native HTTP content and pinned research pages."""
import json
from backend.api.brain_opora.test_canvas_capability_routes import setup, call, SCOPE
from backend.api.editor.test_research_routes import card, edge
from backend.brain_opora.canvas_capabilities import site_reads, research_reads


def test_site_read_adapters_match_native_scoped_routes(setup):
    client, _, auth = setup
    paths = ("", "/tokens.css", "/components.css", "/tokens.json", "/README.md", "/summary", "/proposals")
    for name, suffix in zip(site_reads.NAMES, paths):
        native = client.get("/api/site-admin" + suffix, params={"project": "draft"})
        response = call(client, auth, "site_admin_routes." + name)
        assert response.status_code == native.status_code == 200, response.text
        expected = native.json() if name in ("site_admin_view", "site_admin_summary", "proposal_list") else native.text
        assert response.json()["result"] == expected


def test_research_adapters_preserve_full_sources_pinned_revision_and_paging(setup):
    client, _, auth = setup
    saved = client.post("/api/research", headers=auth, json={**SCOPE, "key": "sources", "operations": [
        card(content="full source " * 2000), card("rc_logic"), edge()]})
    assert saved.status_code == 200, saved.text
    cases = {
        "research_routes.listing": ("/api/research", {"archived": False}),
        "research_routes.detail": ("/api/research/cards/rc_login", {"id": "rc_login", "revision": 1}),
        "research_routes.edge_detail": ("/api/research/edges/re_flow", {"id": "re_flow", "revision": 1}),
        "research_read_routes.topics": ("/api/research/topics", {"archived": False}),
        "research_read_routes.parts": ("/api/research/cards/rc_login/parts", {"id": "rc_login", "revision": 1, "size": 500}),
        "research_read_routes.changes": ("/api/research/events", {"after": 0, "limit": 100}),
    }
    assert set(cases) == set(research_reads.CONTRACTS)
    for capability, (path, data) in cases.items():
        native = client.get(path, params={**SCOPE, **{k: v for k, v in data.items() if k != "id"}}, headers=auth)
        response = call(client, auth, capability, data)
        assert response.status_code == native.status_code == 200, (capability, response.text)
        assert response.json()["result"] == native.json()
    page = call(client, auth, "research_read_routes.parts", {"id": "rc_login", "revision": 1, "size": 500}).json()["result"]
    text = page["text"]
    while page["nextOffset"] is not None:
        page = call(client, auth, "research_read_routes.parts", {"id": "rc_login", "revision": 1,
            "offset": page["nextOffset"], "size": 64000, "snapshot": page["snapshot"]}).json()["result"]
        text += page["text"]
    assert json.loads(text)["content"] == "full source " * 2000
    for bad in (True, "1"):
        assert call(client, auth, "research_routes.detail", {"id": "rc_login", "revision": bad}).status_code == 422
    assert call(client, auth, "research_routes.listing", {"archived": "false"}).status_code == 422


def test_vault_original_read_adapters_match_native_versions(setup, monkeypatch):
    from backend.brain_opora.canvas_capabilities.vault_reads import CONTRACTS
    from backend.integrations import mirror_client
    monkeypatch.setattr(mirror_client, "client_for", lambda project: None)
    client, _, auth = setup
    saved = client.post("/api/brief-vault", headers=auth, json={**SCOPE, "op": "create",
        "scopeNodeId": "", "discipline": "ux", "title": "Original", "text": "Exact original material"})
    assert saved.status_code == 200, saved.text
    identifier = saved.json()["fragment"]["id"]
    duel = client.post("/api/brief-vault", headers=auth, json={**SCOPE, "op": "duel-open",
        "subject": {"kind": "fragment", "id": identifier}, "scopeNodeId": "",
        "incumbent": {"text": "Exact original material"}, "challenger": {"text": "Proposed alternative"}})
    assert duel.status_code == 200, duel.text
    duel_id = duel.json()["fragment"]["id"]
    cases = {
        "tree": ("", {}), "disciplines": ("/disciplines", {}), "next": ("/next", {}),
        "lessons": ("/lessons", {}), "duel": ("/duel", {"id": duel_id}),
        "vision": ("/vision", {}), "fragment": ("/fragment", {"id": identifier, "revision": 1}),
        "history": ("/history", {}), "research_brief": ("/research-brief", {"fragment": identifier}),
        "mirror": ("/mirror", {}), "plan": ("/plan", {"fragmentIds": [identifier]}),
    }
    assert len(cases) == len(CONTRACTS)
    for name, (suffix, data) in cases.items():
        native = (client.post("/api/brief-vault/plan", json={**SCOPE, **data}, headers=auth) if name == "plan"
                  else client.get("/api/brief-vault" + suffix, params={**SCOPE, **data}, headers=auth))
        response = call(client, auth, "brief_vault_routes.brief_vault_" + name, data)
        if name == "plan":
            # This original fragment has not passed synthesis: preserve the native blocked result.
            # The successful full native generated-plan parity lives in test_canvas_capability_vault_extras.
            assert response.status_code == native.status_code == 409, response.text
            assert response.json() == native.json() and response.json()["fragments"]
        else:
            assert response.status_code == native.status_code == 200, (name, response.text)
            assert response.json()["result"] == native.json()
    invalid = call(client, auth, "brief_vault_routes.brief_vault_tree", {"discipline": "not-valid"})
    assert invalid.status_code == 400
