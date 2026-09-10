from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from backend.context_routes import create_context_router
from backend.service import CanvasService

ORIGIN = "http://127.0.0.1:8740"


def make_client(tmp_path):
    """Standalone hostitel: router + stejný ValueError->409 vzor jako app.py, bez app.py."""
    service = CanvasService(tmp_path / "data")
    app = FastAPI()
    app.include_router(create_context_router(service))

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"error": str(exc)}, status_code=409)

    return TestClient(app, base_url=ORIGIN), service


def seed_graph(service):
    nodes = [
        {"id": "sector", "parentId": None, "kind": "sector", "name": "Sektor", "purpose": "", "x": 0, "y": 0},
        {"id": "focus", "parentId": "sector", "kind": "node", "name": "Ohnisko", "purpose": "", "x": 0, "y": 0},
    ]
    view = service.view("draft", "draft")
    service.save_graph("draft", "draft", {"nodes": nodes, "edges": []}, view["digest"])


def base_payload(**overrides):
    payload = {
        "project": "draft",
        "workspace": "draft",
        "node": "focus",
        "includeNodeIds": [],
        "includeJournalDays": [],
        "maxBytes": 50000,
    }
    payload.update(overrides)
    return payload


def test_build_get_and_validate_endpoints(tmp_path):
    client, service = make_client(tmp_path)
    seed_graph(service)

    built = client.post("/api/context/packets", json=base_payload())
    assert built.status_code == 200
    body = built.json()
    packet_id = body["id"]
    assert body["scope"] == {"project": "draft", "workspace": "draft", "node": "focus"}

    loaded = client.get(f"/api/context/packets/{packet_id}")
    assert loaded.status_code == 200
    assert loaded.json() == body

    checked = client.post(f"/api/context/packets/{packet_id}/validate")
    assert checked.status_code == 200
    assert checked.json() == {"id": packet_id, "digest": body["digest"], "stale": False, "changes": []}


def test_invalid_payload_returns_409(tmp_path):
    client, service = make_client(tmp_path)
    seed_graph(service)
    response = client.post("/api/context/packets", json=base_payload(maxBytes=-1))
    assert response.status_code == 409
    assert "error" in response.json()


def test_unknown_packet_id_returns_409(tmp_path):
    client, _service = make_client(tmp_path)
    assert client.get("/api/context/packets/doesnotexist").status_code == 409
    assert client.post("/api/context/packets/doesnotexist/validate").status_code == 409
