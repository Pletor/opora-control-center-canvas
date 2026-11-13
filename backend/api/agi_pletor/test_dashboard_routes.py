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


def test_heart_model(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        assert client.get("/api/pletor/heart/model", headers=HEADERS).json()["model"] == "haiku"
        put = client.put("/api/pletor/heart/model", headers=HEADERS, json={"model": "sonnet", "advisor": "opus"})
        assert put.status_code == 200 and put.json()["model"] == "sonnet"
        assert client.get("/api/pletor/heart/model", headers=HEADERS).json()["model"] == "sonnet"
        with_effort = client.put("/api/pletor/heart/model", headers=HEADERS, json={"model": "sonnet", "advisor": "opus", "effort": "high"})
        assert with_effort.json()["effort"] == "high" and with_effort.json()["efforts"][0] == "low"
        assert client.put("/api/pletor/heart/model", headers=HEADERS, json={"model": "sonnet", "advisor": "opus", "effort": "x"}).status_code == 422
        assert client.get("/api/pletor/heart/model", headers=AGENT).status_code == 403
        assert client.put("/api/pletor/heart/model", headers=AGENT, json={"model": "opus", "advisor": "opus"}).status_code == 403
        bad = client.put("/api/pletor/heart/model", headers=HEADERS, json={"model": "gpt", "advisor": "opus"})
        assert bad.status_code == 422


def test_heart_explain_reads_for_agents_and_caps_only_for_humans(tmp_path):
    # Průhled srdce čte i agent (docs/navrhy/2026-11-13-pruhled-srdce.md §5); stropy mění jen člověk.
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        project = {"project": SCOPE["project"]}
        explained = client.get("/api/pletor/heart/explain", headers=AGENT, params=project)
        assert explained.status_code == 200
        assert {"now", "queue", "stops", "pipeline", "batches", "caps", "model"} <= set(explained.json())
        text = client.get("/api/pletor/heart/explain", headers=AGENT, params={**project, "format": "text"})
        assert text.status_code == 200 and text.text.startswith("SRDCE ") and "ZARÁŽKY" in text.text
        assert client.get("/api/pletor/heart/explain", headers=AGENT, params={"project": "nikde"}).status_code == 404
        assert client.put("/api/pletor/heart/caps", headers=AGENT, json={"per_hour": 12}).status_code == 403
        assert client.put("/api/pletor/heart/caps", headers=HEADERS, json={"per_hour": 12}).json()["per_hour"] == 12
        assert client.put("/api/pletor/heart/caps", headers=HEADERS, json={"per_hour": 0}).status_code == 422
        assert client.get("/api/pletor/heart/caps", headers=HEADERS).json()["per_hour"] == 12
