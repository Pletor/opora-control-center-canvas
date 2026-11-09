"""Actual scoped HTTP adapters preserve original history, native batch replay and CAS."""
from backend.api.brain_opora.test_canvas_capability_routes import call, SCOPE, ORIGIN
from backend.api.editor.test_brief_vault_routes import client_with_sector
from backend.brain_opora.determinism import tokens
from backend.editor.research.test_continuations import imported


def test_original_listing_materialization_native_parity_and_scope(tmp_path):
    with client_with_sector(tmp_path) as client:
        _, _, fragment = imported(client)
        service = client.app.state.service
        _, token = tokens.issue_heart(service, "draft", "draft")
        auth = {"origin": ORIGIN, tokens.HEADER: token}
        prefix = "research_continuation_routes."
        identifier = fragment["id"]
        path = "/api/research/originals/" + identifier
        original = call(client, auth, prefix + "original", {"identifier": identifier})
        assert original.status_code == 200, original.text
        source = original.json()["result"]
        assert source == client.get(path, params=SCOPE, headers=auth).json()
        listed = call(client, auth, prefix + "listing")
        assert listed.status_code == 200, listed.text
        assert listed.json()["result"] == client.get("/api/research/continuations", params=SCOPE, headers=auth).json()
        assert len(listed.json()["result"]["continuations"]) == 1
        data = {"identifier": identifier, "revision": source["sourceRevision"], "detailsRevision": source["detailsRevision"]}
        before = service.view("draft", "draft")["digest"]
        made = call(client, auth, prefix + "materialize", data)
        assert made.status_code == 200 and made.json()["verified"], made.text
        assert call(client, auth, prefix + "materialize", data).json() == made.json()
        native = client.post(path + "/materialize", headers=auth,
                             json={**SCOPE, **{k: v for k, v in data.items() if k != "identifier"}})
        assert native.json() == made.json()["result"]
        card = made.json()["result"]["cards"][0]
        assert card == client.get("/api/research/cards/" + card["id"],
            params={**SCOPE, "revision": card["revision"]}, headers=auth).json()["card"]
        assert card["verification"]["status"] == "unverified"
        after = call(client, auth, prefix + "original", {"identifier": identifier}).json()["result"]
        assert after["sourceHistory"] == source["sourceHistory"] and after["original"] == source["original"]
        assert service.view("draft", "draft")["digest"] == before
        stale = call(client, auth, prefix + "materialize", {**data, "detailsRevision": data["detailsRevision"] + 1})
        assert stale.status_code == 409
        for field in ("revision", "detailsRevision"):
            assert call(client, auth, prefix + "materialize", {**data, field: True}).status_code == 422
        assert call(client, auth, prefix + "original", {"identifier": identifier, "revision": True}).status_code == 422
        assert call(client, auth, prefix + "materialize", data, "not-consumed").status_code == 422
        for name, payload in (("listing", {}), ("original", {"identifier": identifier}), ("materialize", data)):
            for scope in ({**SCOPE, "project": "foreign"}, {**SCOPE, "workspace": "main"}):
                assert call(client, auth, prefix + name, payload, scope=scope).status_code == 403
        assert call(client, auth, prefix + "original", {"identifier": "missing"}).status_code == 404
