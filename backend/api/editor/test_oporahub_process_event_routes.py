"""Live process HTTP: agent-only ingest, no activity-log spam, one merged events feed, wake-on-ingest, health."""
import json
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.editor.opora_event_routes import create_opora_event_router
from backend.app.factory import create_app
from backend.canvas.canvas_service import CanvasService
from backend.canvas.process_ingest import ingest

ORIGIN = "http://127.0.0.1:8740"
AGENT = {"origin": ORIGIN, "x-opora-actor": "agent; name=office-process"}
SCOPE = {"project": "draft", "workspace": "draft"}


def event(seq, **overrides):
    return {"schema": "opora.process-event/1", "id": f"office:f1:{seq}", "seq": seq, "at": "2026-10-22T10:00:00Z",
            "source": "office", "kind": "worker.status", "phase": "work", "state": "start", "title": "Pracovník začal",
            "refs": {**SCOPE, "cardId": "a", "workerId": "w1"}, **overrides}


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as test_client:
        yield test_client


def test_ingest_requires_agent_identity(client):
    body = {"events": [event(1)]}
    client.cookies.clear()
    assert client.post("/api/oporahub/process-events", json=body, headers={"origin": ORIGIN}).status_code == 428
    human = TestClient(client.app, base_url=ORIGIN)
    assert human.post("/api/oporahub/process-events", json=body, headers={"origin": ORIGIN}).status_code == 403
    # without the same Origin even an agent write is refused (factory boundary)
    assert client.post("/api/oporahub/process-events", json=body,
                       headers={"x-opora-actor": "agent; name=x"}).status_code == 403


def test_ingest_validates_dedupes_and_does_not_spam_activity_log(client):
    first = client.post("/api/oporahub/process-events", json={"events": [event(1), event(2, phase="deploy")]},
                        headers=AGENT)
    assert first.status_code == 200, first.text
    assert first.json()["accepted"] == 1 and first.json()["rejected"][0]["index"] == 1
    again = client.post("/api/oporahub/process-events", json={"events": [event(1)]}, headers=AGENT)
    assert again.status_code == 200 and again.json()["duplicates"] == 1
    assert client.post("/api/oporahub/process-events", json={"events": [event(3, schema="x")]},
                       headers=AGENT).status_code == 422
    assert client.post("/api/oporahub/process-events", json={"events": []}, headers=AGENT).status_code == 422
    assert client.get("/api/activity-log", params=SCOPE).json()["entries"] == []
    feed = client.get("/api/oporahub/events", params=SCOPE).json()
    assert [(item["source"], item["kind"], item["eventId"]) for item in feed["events"]] == [
        ("office", "worker.status", "office:f1:1")]
    assert feed["events"][0]["actor"] == {"kind": "agent", "name": "office-process"}


def test_memory_recall_reaches_the_feed_through_the_bridge(client):
    response = client.post("/api/memory/recall", headers=AGENT, json={**SCOPE, "role": None, "nodeId": "a",
                                                                       "query": "x", "maxTokens": 100})
    feed = client.get("/api/oporahub/events", params=SCOPE).json()["events"]
    expected = [("memory.recall", "memory")] if response.status_code == 200 else []
    assert [(item["kind"], item["phase"]) for item in feed] == expected


def test_stream_wakes_on_ingest_instead_of_waiting_for_the_poll(tmp_path):
    service = CanvasService(tmp_path / "data")
    try:
        app = FastAPI()
        # A 3 s poll and a 1 s lifetime: without the wake the stream ends before it reads again.
        app.include_router(create_opora_event_router(service, poll_seconds=3.0, stream_seconds=1.0))
        timer = threading.Timer(0.3, lambda: ingest(service, {"events": [event(1)]}))
        with TestClient(app) as client:
            timer.start()
            body = client.get("/api/oporahub/events/stream", params=SCOPE).text
        timer.join()
        frames = [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]
        assert [(item["source"], item["kind"], item["phase"]) for item in frames] == [
            ("office", "worker.status", "work")]
    finally:
        service.close()


def test_health_reports_office_and_memory(client):
    assert client.get("/api/oporahub/process-health", params=SCOPE).json()["officeConnected"] is False
    client.post("/api/oporahub/process-events", json={"events": [event(1)]}, headers=AGENT)
    health = client.get("/api/oporahub/process-health", params=SCOPE).json()
    assert health["officeConnected"] is True
    assert set(health["sources"]) == {"office", "opora", "github"}
    assert health["memory"]["status"] in {"disabled", "unavailable", "needs_provisioning", "configured"}
    assert client.get("/api/oporahub/process-health", params={"project": "nope", "workspace": "x"}).status_code == 404
