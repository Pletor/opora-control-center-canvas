"""Cesta `/api/canvas-plan`: strop těla 2 MiB (ostatní zápisy mají 2 MB) a chyba jako 409."""
import json

from fastapi.testclient import TestClient

from backend.app.factory import create_app

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN, "content-type": "application/json"}
SCOPE = {"project": "draft", "workspace": "draft"}


def body_of(digest, size):
    """Dávka s textem karet tak dlouhým, aby tělo mělo přesně `size` bajtů."""
    cards = 40
    plan = {"nodes": [{"ref": f"k{i}", "kind": "node", "name": f"Karta {i}", "text": ""} for i in range(cards)]}
    payload = {**SCOPE, "digest": digest, "dryRun": True, "plan": plan}
    filler = size - len(json.dumps(payload).encode())
    for i, item in enumerate(plan["nodes"]):
        item["text"] = "x" * (filler // cards + (1 if i < filler % cards else 0))
    raw = json.dumps(payload).encode()
    assert len(raw) == size
    return raw


def test_plan_up_to_two_mib_passes_the_body_limit(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        digest = client.get("/api/view", params=SCOPE).json()["digest"]
        fits = client.post("/api/canvas-plan", headers=HEADERS, content=body_of(digest, 2 * 1024 * 1024))
        assert fits.status_code == 200, fits.text[:200]
        assert fits.json()["summary"] == "Přidá 40 karet, text u 40 karet."
        too_big = client.post("/api/canvas-plan", headers=HEADERS, content=body_of(digest, 2 * 1024 * 1024 + 1))
        assert too_big.status_code == 413
        # Ostatní zápisy drží dosavadní strop 2 MB.
        graph = client.post("/api/graph", headers=HEADERS, content=b" " * 2_000_001)
        assert graph.status_code == 413


def test_plan_error_is_409_with_item_name(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        digest = client.get("/api/view", params=SCOPE).json()["digest"]
        response = client.post("/api/canvas-plan", headers=HEADERS, json={
            **SCOPE, "digest": digest, "plan": {"nodes": [{"ref": "Spatne", "kind": "node", "name": "X"}]},
        })
        assert response.status_code == 409
        assert "ref musí být" in response.json()["error"]
