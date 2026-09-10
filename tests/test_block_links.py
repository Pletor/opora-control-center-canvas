from fastapi.testclient import TestClient

from backend.app import create_app

ORIGIN = "http://127.0.0.1:8740"
NODES = [("sector", None, "sector"), ("alfa", "sector", "node"), ("beta", "sector", "node")]


def graph_payload(digest):
    nodes = [
        {"id": key, "parentId": parent, "kind": kind, "name": key.capitalize(), "purpose": "", "x": 0, "y": 0}
        for key, parent, kind in NODES
    ]
    edges = [{"id": "e1", "source": "alfa", "target": "beta"}]
    return {"project": "draft", "workspace": "draft", "digest": digest, "graph": {"nodes": nodes, "edges": edges}}


def test_block_links_resolve_existing_nodes_and_report_real_counts(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        view = client.get("/api/view").json()
        assert client.post("/api/graph", headers={"origin": ORIGIN}, json=graph_payload(view["digest"])).status_code == 200
        scope = {"project": "draft", "workspace": "draft"}
        # Text s odkazem podle jména, podle ID a s neexistujícím cílem.
        client.post(
            "/api/node-text",
            headers={"origin": ORIGIN},
            json={**scope, "node": "alfa", "expected_revision": 0, "text": "- vede na [[Beta]]\n- a na [[sector]]\n- a na [[Neexistuje]]"},
        )
        client.post(
            "/api/node-text",
            headers={"origin": ORIGIN},
            json={**scope, "node": "beta", "expected_revision": 0, "text": "- zpět na [[Alfa]] <script>alert(1)</script>"},
        )

        targets = client.get("/api/node-links/targets", params=scope).json()["targets"]
        assert {t["id"] for t in targets} == {"sector", "alfa", "beta"}

        alfa = client.get("/api/node-links", params={**scope, "node": "alfa"}).json()
        assert [(l["nodeId"], l["via"]) for l in alfa["outgoing"]] == [("beta", "text"), ("sector", "text")]
        assert alfa["unresolved"] == ["Neexistuje"]
        assert [(l["nodeId"], l["via"], l["direction"]) for l in alfa["backlinks"]] == [("beta", "text", "in")]
        assert [(l["nodeId"], l["direction"]) for l in alfa["edges"]] == [("beta", "out")]
        # Skutečné počty, nikoli odhad: 2 odkazy z textu, 1 zpětný, 1 hrana grafu.
        assert alfa["counts"] == {"outgoing": 2, "backlinks": 1, "edges": 1, "unresolved": 1}

        beta = client.get("/api/node-links", params={**scope, "node": "beta"}).json()
        assert [l["nodeId"] for l in beta["backlinks"]] == ["alfa"]
        assert [(l["nodeId"], l["direction"]) for l in beta["edges"]] == [("alfa", "in")]
        # Odkaz nese jen identitu existujícího uzlu; text zůstává neinterpretovaný.
        assert beta["outgoing"][0]["name"] == "Alfa" and beta["outgoing"][0]["kind"] == "node"

        assert client.get("/api/node-links", params={**scope, "node": "chybi"}).status_code == 409
        main = client.get("/api/node-links", params={"project": "draft", "workspace": "main", "node": "alfa"})
        assert main.status_code == 409
