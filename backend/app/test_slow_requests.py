import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import slow_requests


def test_only_slow_requests_are_kept_longest_first(monkeypatch):
    monkeypatch.setattr(slow_requests, "_RECENT", type(slow_requests._RECENT)(maxlen=5))
    now = time.perf_counter()
    slow_requests.note("GET", "/fast", "p", now, 200, now=1000.0)
    slow_requests.note("POST", "/api/brain/heart/brief", "p", now - 60, 200, now=1000.0)
    slow_requests.note("GET", "/api/oporahub/agent-state", "p", now - 18, 200, now=1000.0)
    found = slow_requests.recent(900.0)
    assert [(item["path"], round(item["ms"] / 1000)) for item in found] == [
        ("/api/brain/heart/brief", 60), ("/api/oporahub/agent-state", 18)]
    assert round(found[0]["at"]) == 940  # začátek požadavku, ne konec
    assert slow_requests.recent(1001.0) == []


def test_factory_middleware_records_path_and_project(monkeypatch):
    seen = []
    monkeypatch.setattr(slow_requests, "note", lambda *args: seen.append(args[:3] + args[4:]))
    from backend.app.factory import track_slow
    app = FastAPI()
    track_slow(app)
    app.get("/x")(lambda: {"ok": True})
    assert TestClient(app).get("/x?project=abc").status_code == 200
    assert seen == [("GET", "/x", "abc", 200)]
