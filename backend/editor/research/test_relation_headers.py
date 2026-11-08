"""Header navigation counts are scoped projections, never stored card truth."""
from backend.api.editor.test_brief_vault_routes import client_with_sector
from backend.api.editor.test_research_routes import card, edge, post
from backend.editor.node.test_removals import HEADERS, SCOPE
from backend.brain_opora.determinism import tokens


def test_directional_headers_follow_visible_edges_without_changing_revisions(tmp_path):
    with client_with_sector(tmp_path) as client:
        assert post(client, [card(), card("rc_logic"), card("rc_end"), edge(),
                            edge(id="re_next", fromId="rc_logic", toId="rc_end")]).status_code == 200

        def counts(**params):
            response = client.get("/api/research", params={**SCOPE, **params})
            assert response.status_code == 200
            return {c["id"]: c["relationCounts"] for c in response.json()["cards"]}

        assert counts() == {"rc_login": {"incoming": 0, "outgoing": 1},
                            "rc_logic": {"incoming": 1, "outgoing": 1},
                            "rc_end": {"incoming": 1, "outgoing": 0}}
        assert post(client, [{"op": "archive", "entity": "edge", "id": "re_flow",
                              "expectedRevision": 1, "archived": True}], "hide-edge").status_code == 200
        assert counts()["rc_logic"] == {"incoming": 0, "outgoing": 1}
        assert counts(archived=1)["rc_logic"] == {"incoming": 1, "outgoing": 1}
        assert post(client, [{"op": "archive", "entity": "card", "id": "rc_end",
                              "expectedRevision": 1, "archived": True}], "hide-card").status_code == 200
        assert counts()["rc_logic"] == {"incoming": 0, "outgoing": 0}
        detail = client.get("/api/research/cards/rc_logic", params=SCOPE).json()
        assert detail["card"]["revision"] == 1 and "relationCounts" not in detail["card"]
        session = tokens.issue_worker(client.app.state.service, "draft", "draft", {"name": "reader"})
        headers = {**HEADERS, "X-Opora-Actor": "agent; name=reader", tokens.HEADER: session["token"]}
        for field in ("project", "workspace"):
            assert client.get("/api/research", params={**SCOPE, field: "foreign"}, headers=headers).status_code == 403
