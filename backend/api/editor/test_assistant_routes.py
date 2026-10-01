"""Routy asistenta přes TestClient nad falešným CLI; skutečný `claude` se nikdy nespouští."""

import asyncio
import json
import sys
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from backend.api.editor.assistant_routes import create_assistant_router, sse_events
from backend.app.factory import create_app
from backend.claude_code.assistant import fake_cli
from backend.claude_code.assistant.manager import AssistantManager, Limits

FAKE = str(Path(fake_cli.__file__))
SID = "0f8fad5b-d9cb-469f-a165-70867728950e"


def fake_builder(claude, model, resume):
    return [sys.executable, FAKE] + (["--resume", resume] if resume else [])


@pytest.fixture
def setup(tmp_path):
    root = tmp_path / "projekt"
    root.mkdir()

    def locate(project, workspace=None):
        if project != "p1":
            raise ValueError("Neplatný identifikátor projektu.")
        return workspace or "draft", root

    manager = AssistantManager(tmp_path / "data", locate, which=lambda name: "fake-claude",
                               command_builder=fake_builder, limits=Limits(tick_seconds=3600),
                               home=tmp_path, version_probe=lambda path: "9.9.9 (fake)")
    app = FastAPI()

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"error": str(exc)}, status_code=409)

    app.include_router(create_assistant_router(manager, heartbeat_seconds=0.05, poll_seconds=0.01))
    with TestClient(app) as client:
        yield client, manager, tmp_path
    manager.close_all()


def wait_idle(manager, sid, turns=1):
    end = time.monotonic() + 20
    while time.monotonic() < end:
        if [e["type"] for e in manager.events(sid)[0]].count("turn_end") >= turns:
            return
        time.sleep(0.02)
    raise AssertionError("Tah neskončil.")


def frames(body):
    return [json.loads(chunk.split("data: ", 1)[1]) for chunk in body.split("\n\n") if "data: " in chunk]


def test_status_and_session_lifecycle(setup):
    client, manager, _ = setup
    assert client.get("/api/assistant/status").json() == {
        "available": True, "claudePath": "fake-claude", "version": "9.9.9 (fake)", "running": 0, "limit": 3}
    created = client.post("/api/assistant/sessions", json={"project": "p1", "model": "sonnet"})
    assert created.status_code == 201
    session = created.json()["session"]
    assert session["model"] == "sonnet" and session["workspace"] == "draft" and session["lastSeq"] == 0
    assert session["state"] == "idle" and session["title"] == "Nový úkol"
    sid = session["id"]

    sent = client.post(f"/api/assistant/sessions/{sid}/messages",
                       json={"text": "Ahoj", "context": {"projectId": "p1", "environment": "project"}})
    assert sent.status_code == 202 and sent.json() == {"accepted": True, "seq": 1}
    wait_idle(manager, sid)
    listed = client.get("/api/assistant/sessions", params={"project": "p1"}).json()["sessions"]
    assert len(listed) == 1 and listed[0]["lastSeq"] == 6 and listed[0]["title"] == "Ahoj"
    assert listed[0]["claudeSessionId"]

    stopped = client.post(f"/api/assistant/sessions/{sid}/stop", json={})
    assert stopped.status_code == 200 and stopped.json()["session"]["state"] == "idle"
    closed = client.post(f"/api/assistant/sessions/{sid}/close", json={})
    assert closed.json()["session"]["state"] == "closed"
    assert client.get("/api/assistant/sessions", params={"project": "p1"}).json() == {"sessions": []}


def test_validation_and_errors(setup):
    client, manager, _ = setup
    assert client.post("/api/assistant/sessions", json={"project": "zzz"}).status_code == 409
    assert client.post("/api/assistant/sessions", json={"project": "p1", "extra": 1}).status_code == 409
    assert client.post("/api/assistant/sessions", json={"project": "p1", "model": "haiku"}).status_code == 409
    sid = client.post("/api/assistant/sessions", json={"project": "p1"}).json()["session"]["id"]
    missing = client.post("/api/assistant/sessions/nope/messages", json={"text": "x"})
    assert missing.status_code == 404 and missing.json() == {"error": "Session asistenta neexistuje."}
    assert client.get("/api/assistant/sessions/nope/events").status_code == 404
    bad = client.post(f"/api/assistant/sessions/{sid}/messages",
                      json={"text": "x", "context": {"selectedNodeIds": ["n"] * 51}})
    assert bad.status_code == 409 and "selectedNodeIds" in bad.json()["error"]
    assert client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "x" * 20001}).status_code == 409
    assert client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "SLEEP"}).status_code == 202
    busy = client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "znovu"})
    assert busy.status_code == 409 and "odpovídá" in busy.json()["error"]


def test_sse_replays_after_seq_and_ends_on_close(setup):
    client, manager, _ = setup
    sid = client.post("/api/assistant/sessions", json={"project": "p1"}).json()["session"]["id"]
    client.post(f"/api/assistant/sessions/{sid}/messages", json={"text": "Ahoj"})
    wait_idle(manager, sid)
    client.post(f"/api/assistant/sessions/{sid}/close", json={})
    response = client.get(f"/api/assistant/sessions/{sid}/events", params={"after": 2})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text.startswith("id: 3\nevent: message\ndata: ")
    events = frames(response.text)
    assert [event["seq"] for event in events] == [3, 4, 5, 6, 7]
    assert [event["type"] for event in events] == ["text_delta", "message", "turn_end", "status", "status"]
    assert events[-1]["state"] == "closed"
    replay = client.get(f"/api/assistant/sessions/{sid}/events", headers={"Last-Event-ID": "5"})
    assert [event["seq"] for event in frames(replay.text)] == [6, 7]
    everything = client.get(f"/api/assistant/sessions/{sid}/events")
    assert frames(everything.text)[0] == {"seq": 1, "type": "message", "role": "user", "text": "Ahoj"}


def test_sse_generator_sends_heartbeat_and_stops_on_disconnect():
    class Quiet:
        def events(self, session_id, after):
            return [], False

    calls = {"n": 0}

    async def disconnected():
        calls["n"] += 1
        return calls["n"] > 8

    async def collect():
        return [chunk async for chunk in sse_events(Quiet(), "s", 0, disconnected, heartbeat=0.0, poll=0.001)]

    chunks = asyncio.run(collect())
    assert chunks and all(chunk == ": ping\n\n" for chunk in chunks)


def test_transcript_from_injected_home(setup):
    client, manager, tmp_path = setup
    sid = client.post("/api/assistant/sessions", json={"project": "p1"}).json()["session"]["id"]
    assert client.get(f"/api/assistant/sessions/{sid}/transcript").json() == {"messages": []}
    manager.registry.update(sid, claudeSessionId=SID)
    folder = tmp_path / ".claude" / "projects" / "C--projekt"
    folder.mkdir(parents=True)
    lines = [
        {"type": "user", "message": {"content": '<opora_context>{"projectId":"p1"}</opora_context>\n\nAhoj'}},
        {"type": "assistant", "message": {"id": "m1", "content": [{"type": "text", "text": "Dobrý den."}]}},
    ]
    (folder / f"{SID}.jsonl").write_text("\n".join(json.dumps(item) for item in lines), encoding="utf-8")
    assert client.get(f"/api/assistant/sessions/{sid}/transcript").json() == {"messages": [
        {"role": "user", "text": "Ahoj"}, {"role": "assistant", "text": "Dobrý den."}]}


def test_factory_registers_assistant_routes(tmp_path):
    with TestClient(create_app(tmp_path), base_url="http://127.0.0.1:8740") as client:
        assert client.get("/api/assistant/sessions", params={"project": "p1"}).json() == {"sessions": []}
        missing = client.post("/api/assistant/sessions/nope/stop", json={},
                              headers={"origin": "http://127.0.0.1:8740"})
        assert missing.status_code == 404


def test_title_endpoint(setup):
    client, manager, _ = setup
    sid = client.post("/api/assistant/sessions", json={"project": "p1"}).json()["session"]["id"]
    url = f"/api/assistant/sessions/{sid}/title"
    ok = client.post(url, json={"title": "  Nový název  "})
    assert ok.status_code == 200
    assert ok.json()["session"]["title"] == "Nový název" and ok.json()["session"]["lastSeq"] == 0
    assert client.get("/api/assistant/sessions", params={"project": "p1"}).json()["sessions"][0]["title"] == "Nový název"
    for bad in ({"title": ""}, {"title": "x" * 81}, {"title": "a\tb"}, {"title": 3}, {}, {"title": "a", "x": 1}):
        assert client.post(url, json=bad).status_code == 409
    missing = client.post("/api/assistant/sessions/nope/title", json={"title": "A"})
    assert missing.status_code == 404
    client.post(f"/api/assistant/sessions/{sid}/close", json={})
    assert client.post(url, json={"title": "Po zavření"}).status_code == 409
