"""Hook control vrácený bez Live Run (upgrade-opora #38): vazbu a řízení dělá jen člověk."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=hooked"}


def test_agent_cannot_bind_control_or_install_hooks(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        for route in ("/api/agent-hooks/bind", "/api/agent-hooks/control", "/api/agent-hooks/vscode"):
            assert client.post(route, headers=AGENT, json={}).status_code == 403, route
        client.cookies.clear()
        assert client.post("/api/agent-hooks/bind", headers=HEADERS, json={}).status_code == 428


def test_hook_event_without_valid_token_stops_the_agent(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        answer = client.post("/api/agent-hooks/event", headers=HEADERS, json={"bindingId": "x", "event": {}})
        assert answer.status_code == 200 and answer.json()["continue"] is False
