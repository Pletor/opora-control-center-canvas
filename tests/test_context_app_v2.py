from fastapi.testclient import TestClient

from backend.app import create_app


def test_context_router_is_integrated_without_starting_an_agent(tmp_path):
    origin = "http://127.0.0.1:8740"
    with TestClient(create_app(tmp_path), base_url=origin) as client:
        response = client.post("/api/context/packets", headers={"Origin": origin}, json={})
        assert response.status_code == 409, "Chybí zapojení vytvořeného context modulu do skutečné aplikace"
        assert "kontext" in response.json()["error"].lower()
