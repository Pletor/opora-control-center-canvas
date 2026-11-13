"""Pojistky přes aplikaci: čte agent i člověk, člověk přepíná vždy, agent jen agent_may_toggle s důvodem."""
from fastapi.testclient import TestClient

from backend.app import error_log, errors, guards
from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN

AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=dev"}


def test_read_and_toggle_rules(tmp_path):
    try:
        with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
            body = client.get("/api/pletor/guards", headers=AGENT).json()
            rows = {row["id"]: row for row in body["guards"]}
            assert rows["content_manifest"]["mode"] == "enforce" and rows["content_manifest"]["protects"]
            assert rows["heart_hour_cap"]["linked"] == "PUT /api/pletor/heart/caps" and "value" in rows["heart_hour_cap"]
            assert rows["sql_context_pin"]["wired"] is False
            text = client.get("/api/pletor/guards", headers=HEADERS, params={"format": "text"}).text
            assert "content_manifest: enforce (default)" in text and "heart_hour_cap: propojený přepínač" in text

            put = lambda guard, body, headers: client.put(f"/api/pletor/guards/{guard}", json=body, headers=headers)
            assert put("budget", {"mode": "off", "reason": "chci"}, AGENT).status_code == 403
            assert put("content_manifest", {"mode": "warn", "reason": "  "}, AGENT).status_code == 403
            done = put("content_manifest", {"mode": "warn", "reason": "nová karta z plánu"}, AGENT)
            assert done.status_code == 200 and guards.mode("content_manifest", "x") == "warn"
            assert put("budget", {"mode": "warn"}, HEADERS).status_code == 200 and guards.mode("budget") == "warn"
            assert put("heart_hour_cap", {"mode": "off"}, HEADERS).status_code == 422
            assert put("budget", {"mode": "loud"}, HEADERS).status_code == 422
            assert put("budget", {"mode": "off", "project": "neni"}, HEADERS).status_code == 404
            error_log.drain()
            changes = [r for r in errors.read() if r["kind"] == "guard"]
            assert {(r["actor_kind"], r["actor_name"]) for r in changes} == {("agent", "dev"), ("human", None)}
    finally:
        guards.configure(None)
        errors.configure(None)
