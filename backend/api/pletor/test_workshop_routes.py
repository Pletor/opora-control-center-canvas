"""Routy Dílny D0 přes skutečnou aplikaci: seznam, měření ukázky, 404, 422 a jen člověk."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN

AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=dev"}
BASE = "/api/pletor/workshop/tools"


def test_workshop_routes(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        tools = client.get(BASE, headers=HEADERS)
        assert tools.status_code == 200
        assert {"name": "rozdel_vety", "path": "rozdel_vety.py", "cases": 4} in tools.json()["tools"]
        measured = client.post(f"{BASE}/rozdel_vety/measure", headers=HEADERS, json={})
        assert measured.status_code == 200
        assert measured.json()["passed"] == 4 and measured.json()["deterministic"] is True
        assert client.post(f"{BASE}/neni/measure", headers=HEADERS, json={}).status_code == 404
        assert client.post(f"{BASE}/Spatny-nazev/measure", headers=HEADERS, json={}).status_code == 422
        assert client.get(BASE, headers=AGENT).status_code == 403
        assert client.post(f"{BASE}/rozdel_vety/measure", headers=AGENT, json={}).status_code == 403
