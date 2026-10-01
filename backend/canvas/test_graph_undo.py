"""Krok zpět na plátně (Ctrl+Z): uložení s `undo` smí uzel z grafu vypustit, ale nic nemaže.

Vznik uzlu, komentáře, oblasti i vazby musí jít vzít zpět. Server proto u `undo: true` pustí
snímek, ve kterém uzel chybí, a nesahá přitom na obsah karty: text, stav Desktop v3 i vše
ostatní zůstává, takže krok vpřed (stejné ID zpátky do grafu) vrátí kartu i s obsahem.
"""

from fastapi.testclient import TestClient

from backend.app.factory import create_app

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
SCOPE = {"project": "draft", "workspace": "draft"}
EMPTY_STATE = {"settings": [], "rules": [], "decisions": [], "nodes": {}, "tickets": [], "edges": {}}

SEKTOR = {"id": "sektor", "parentId": None, "kind": "sector", "name": "Sektor", "purpose": "", "x": 0, "y": 0}
KARTA = {"id": "karta", "parentId": "sektor", "kind": "node", "name": "Karta", "purpose": "Podstata", "x": 40, "y": 60}
SOUSED = {"id": "soused", "parentId": "sektor", "kind": "node", "name": "Soused", "purpose": "", "x": 300, "y": 60}
VAZBA = {"id": "vazba", "source": "soused", "target": "karta", "port": "next"}

BEFORE = {"nodes": [SEKTOR, SOUSED], "edges": []}
AFTER = {"nodes": [SEKTOR, SOUSED, KARTA], "edges": [VAZBA]}


def save(client, graph, digest, **extra):
    return client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": graph, "digest": digest, **extra})


def digest_now(client):
    return client.get("/api/view", params=SCOPE).json()["digest"]


def seed(client):
    """Plátno po vzniku karty: `BEFORE` je snímek, který si historie odložila před změnou."""
    assert save(client, BEFORE, digest_now(client)).status_code == 200
    assert save(client, AFTER, digest_now(client)).status_code == 200


def test_plain_save_still_refuses_to_drop_a_node(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed(client)
        refused = save(client, BEFORE, digest_now(client))
        assert refused.status_code == 409
        assert "Mazání" in refused.json()["error"]
        # Ani `undo: false` nebo jiná hodnota než pravda kartu nevypustí.
        assert save(client, BEFORE, digest_now(client), undo=False).status_code == 409
        assert save(client, BEFORE, digest_now(client), undo="true").status_code == 409
        assert [n["id"] for n in client.get("/api/view", params=SCOPE).json()["graph"]["nodes"]] == [
            "sektor", "soused", "karta"
        ]


def test_undo_drops_the_node_from_the_graph_and_redo_brings_its_content_back(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed(client)
        text = "Obsah karty, který krok zpět nesmí ztratit."
        saved_text = client.post(
            "/api/node-text", headers=HEADERS,
            json={**SCOPE, "node": "karta", "expected_revision": 0, "text": text},
        )
        assert saved_text.status_code == 200, saved_text.text
        assert saved_text.json()["revision"] == 1
        state = {
            **EMPTY_STATE,
            "nodes": {"karta": {
                "phase": "build",
                "criteria": [{"id": "c1", "text": "Testy zelené", "checked": True}],
                "steps": [{"id": "s1", "text": "Napsat test", "assignee": "builder", "done": False}],
            }},
        }
        saved_state = client.post(
            "/api/desktop-v3/state", headers=HEADERS,
            json={**SCOPE, "expectedRevision": 0, "state": state},
        )
        assert saved_state.status_code == 200, saved_state.text

        stepped = save(client, BEFORE, digest_now(client), undo=True)
        assert stepped.status_code == 200, stepped.text
        assert [n["id"] for n in stepped.json()["graph"]["nodes"]] == ["sektor", "soused"]
        assert stepped.json()["graph"]["edges"] == []

        # Z grafu karta zmizela, obsah ale zůstal: revize textu i zápis ve stavu Desktop v3.
        assert client.get("/api/node-text", params={**SCOPE, "node": "karta"}).status_code == 409
        assert client.get("/api/desktop-v3/state", params=SCOPE).json()["state"]["nodes"]["karta"]["phase"] == "build"

        back = save(client, AFTER, digest_now(client))
        assert back.status_code == 200, back.text
        restored = client.get("/api/node-text", params={**SCOPE, "node": "karta"}).json()
        assert restored["text"] == text
        assert restored["revision"] == 1
        brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "karta"})
        assert brief.status_code == 200, brief.text
        assert brief.json()["harness"]["phase"] == "build"
        assert brief.json()["harness"]["steps"][0]["text"] == "Napsat test"


def test_undo_snapshot_must_stay_consistent(tmp_path):
    """Krok zpět není povolení k rozbitému grafu: osiřelá vazba ani potomek bez sektoru neprojdou."""
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        seed(client)
        orphan_edge = {"nodes": [SEKTOR, SOUSED], "edges": [VAZBA]}
        assert save(client, orphan_edge, digest_now(client), undo=True).status_code == 409
        orphan_child = {"nodes": [SOUSED, KARTA], "edges": []}
        assert save(client, orphan_child, digest_now(client), undo=True).status_code == 409
        assert [n["id"] for n in client.get("/api/view", params=SCOPE).json()["graph"]["nodes"]] == [
            "sektor", "soused", "karta"
        ]
