"""Deník chyb přes aplikaci: JSON i text, čte i agent, neplatný limit 422."""
from fastapi.testclient import TestClient

from backend.app import errors
from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN

AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=dev"}


def test_errors_json_and_text(tmp_path):
    try:
        with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
            errors.record("heart", "timeout", "brief vypršel po 60 s", project="p", lever="průhled srdce")
            errors.record("flow", "log", "jiný projekt", project="q")
            body = client.get("/api/pletor/errors", headers=AGENT, params={"project": "p"}).json()
            assert body["open"] == 1 and [(r["source"], r["count"]) for r in body["errors"]] == [("heart", 1)]
            text = client.get("/api/pletor/errors", headers=HEADERS, params={"format": "text", "source": "heart"})
            assert text.status_code == 200 and text.text.startswith("[error] heart/timeout · p · 1×")
            assert client.get("/api/pletor/errors", headers=HEADERS, params={"limit": 0}).status_code == 422
    finally:
        errors.configure(None)
