"""Routy velínu přes skutečnou aplikaci: 200 pro všechny čtyři, 403 bez člověka, 422 špatný projekt, 404 neznámý."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed

AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=dev"}


def test_dashboard_reads(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        heart = client.get("/api/pletor/heart", headers=HEADERS, params=SCOPE)
        assert heart.status_code == 200 and set(heart.json()) == {"status", "queue", "batches", "gate", "brain"}
        assert heart.json()["status"]["running"] is False
        context = client.get("/api/pletor/context", headers=HEADERS, params=SCOPE)
        assert context.status_code == 200 and context.json()["text"].startswith("PODKLADY")
        assert {s["title"] for s in context.json()["sections"]} >= {"STAV SRDCE"}
        assert all(set(s) == {"title", "chars", "cap", "truncated"} for s in context.json()["sections"])
        messages = client.get("/api/pletor/messages", headers=HEADERS, params={**SCOPE, "limit": 5, "q": "x"})
        assert messages.status_code == 200 and messages.json() == {"messages": [], "total": 0}
        monitoring = client.get("/api/pletor/monitoring", headers=HEADERS, params={"project": SCOPE["project"]})
        assert monitoring.status_code == 200
        assert monitoring.json() == {"hosts": [], "events": [], "enabled": False}


def test_dashboard_refusals(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        for path in ("heart", "context", "messages", "monitoring"):
            assert client.get(f"/api/pletor/{path}", headers=AGENT, params=SCOPE).status_code == 403
            assert client.get(f"/api/pletor/{path}", headers=HEADERS, params={"project": "špatné id"}).status_code == 422
            gone = client.get(f"/api/pletor/{path}", headers=HEADERS, params={**SCOPE, "project": "nikde"})
            assert gone.status_code == 404
        assert client.get("/api/pletor/messages", headers=HEADERS, params={**SCOPE, "limit": 0}).status_code == 422
