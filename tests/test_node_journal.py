from fastapi.testclient import TestClient

from backend.app import create_app

ORIGIN = "http://127.0.0.1:8740"


def prepared(client):
    view = client.get("/api/view").json()
    nodes = [
        {"id": key, "parentId": parent, "kind": kind, "name": key.capitalize(), "purpose": "", "x": 0, "y": 0}
        for key, parent, kind in [("sector", None, "sector"), ("alfa", "sector", "node")]
    ]
    assert client.post(
        "/api/graph",
        headers={"origin": ORIGIN},
        json={"project": "draft", "workspace": "draft", "digest": view["digest"], "graph": {"nodes": nodes, "edges": []}},
    ).status_code == 200


def test_journal_entries_are_dated_revisioned_blocks_of_the_same_node(tmp_path):
    root = tmp_path / "data"
    scope = {"project": "draft", "workspace": "draft", "node": "alfa"}
    with TestClient(create_app(root), base_url=ORIGIN) as client:
        prepared(client)
        empty = client.get("/api/node-journal", params={**scope, "day": "2026-09-10"}).json()
        assert empty["revision"] == 0 and empty["text"] == "" and empty["days"] == []
        assert empty["scope"] == {"project": "draft", "workspace": "draft", "node": "alfa", "day": "2026-09-10"}

        first = client.post(
            "/api/node-journal",
            headers={"origin": ORIGIN},
            json={**scope, "day": "2026-09-10", "expected_revision": 0, "text": "- rozhodnutí dne\n\t- odkaz na [[Sector]]"},
        )
        assert first.status_code == 200 and first.json()["revision"] == 1
        assert first.json()["saved_at"] is not None

        # CAS: zastaralá revize nesmí tiše přepsat cizí zápis.
        assert client.post(
            "/api/node-journal",
            headers={"origin": ORIGIN},
            json={**scope, "day": "2026-09-10", "expected_revision": 0, "text": "stale"},
        ).status_code == 409

        assert client.post(
            "/api/node-journal",
            headers={"origin": ORIGIN},
            json={**scope, "day": "2026-09-09", "expected_revision": 0, "text": "- včerejší zápis"},
        ).json()["revision"] == 1

        listing = client.get("/api/node-journal", params={**scope, "day": "2026-09-10"}).json()
        assert [d["day"] for d in listing["days"]] == ["2026-09-10", "2026-09-09"]
        assert listing["days"][0]["revision"] == 1

        # Neplatné datum, neexistující uzel a main jsou odmítnuté, nikoli tiše uložené.
        for day in ["10.9.2026", "2026-13-01", "", "2026-09-10T00:00"]:
            assert client.get("/api/node-journal", params={**scope, "day": day}).status_code == 409
        assert client.get("/api/node-journal", params={**scope, "node": "chybi", "day": "2026-09-10"}).status_code == 409
        assert client.get("/api/node-journal", params={**scope, "workspace": "main", "day": "2026-09-10"}).status_code == 409
        assert client.post(
            "/api/node-journal",
            headers={"origin": ORIGIN},
            json={**scope, "workspace": "main", "day": "2026-09-10", "expected_revision": 0, "text": "x"},
        ).status_code == 409

    with TestClient(create_app(root), base_url=ORIGIN) as client:
        after_reload = client.get("/api/node-journal", params={**scope, "day": "2026-09-10"}).json()
        assert after_reload["text"] == "- rozhodnutí dne\n\t- odkaz na [[Sector]]"
        assert after_reload["revision"] == 1
