"""Správce session nad falešným CLI (`fake_cli.py`); skutečný `claude` se nikdy nespouští."""

import os
import sys
import time
from pathlib import Path

import pytest

from backend.claude_code.assistant import fake_cli
from backend.claude_code.assistant.manager import (
    AssistantError,
    AssistantManager,
    AssistantUnavailable,
    Limits,
    SessionNotFound,
)

FAKE = Path(fake_cli.__file__)


def fake_builder(claude, model, resume):
    return [sys.executable, str(FAKE)] + (["--resume", resume] if resume else [])


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make(tmp_path, *, limits=None, clock=None, which=lambda name: "fake-claude"):
    root = tmp_path / "projekt"
    root.mkdir(exist_ok=True)

    def locate(project, workspace=None):
        if project == "nope":
            raise ValueError("Neplatný identifikátor projektu.")
        return workspace or "draft", root

    return AssistantManager(tmp_path / "data", locate, which=which, command_builder=fake_builder,
                            environ={**os.environ,"ANTHROPIC_API_KEY": "sk-test"},
                            limits=limits or Limits(tick_seconds=3600), clock=clock or Clock(),
                            home=tmp_path, version_probe=lambda path: "9.9.9 (fake)")


def wait_for(predicate, timeout=20):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.02)
    raise AssertionError("Podmínka se nesplnila včas.")


def types(manager, sid):
    return [event["type"] for event in manager.events(sid)[0]]


def idle_after_turn(manager, sid, turns=1):
    wait_for(lambda: types(manager, sid).count("turn_end") >= turns)


def assistant_texts(manager, sid):
    return [e["text"] for e in manager.events(sid)[0] if e["type"] == "message" and e["role"] == "assistant"]


@pytest.fixture
def manager(tmp_path):
    instance = make(tmp_path)
    yield instance
    instance.close_all()


def test_full_turn_maps_events_and_stores_session(manager):
    sid = manager.create("p1")["id"]
    context = {"projectId": "p1", "selectedNodeIds": ["n1"], "environment": "editor"}
    accepted = manager.send(sid, "Co dál s kartou?", context)
    assert accepted == {"seq": 1, "type": "message", "role": "user", "text": "Co dál s kartou?"}
    idle_after_turn(manager, sid)
    assert types(manager, sid) == ["message", "status", "text_delta", "message", "turn_end", "status"]
    events = manager.events(sid)[0]
    assert [event["seq"] for event in events] == [1, 2, 3, 4, 5, 6]
    assert events[2] == {"seq": 3, "type": "text_delta", "messageId": "msg_1", "text": "ok"}
    reply = events[3]["text"]
    assert "resume=none" in reply and "apikey=unset" in reply and "cwd=projekt" in reply
    assert 'got=<opora_context>{"projectId":"p1","selectedNodeIds":["n1"],"environment":"editor"}</opora_context>' in reply
    record = manager.session(sid)
    assert record["claudeSessionId"] and record["state"] == "idle" and record["lastSeq"] == 6
    assert record["title"] == "Co dál s kartou?"
    # Další zpráva jde do téhož procesu, bez --resume.
    manager.send(sid, "A potom?")
    idle_after_turn(manager, sid, 2)
    assert "resume=none" in assistant_texts(manager, sid)[-1]
    assert manager.running() == 1
    assert manager.status() == {"available": True, "claudePath": "fake-claude", "version": "9.9.9 (fake)",
                                "running": 1, "limit": 3}


def test_busy_turn_stop_and_resume(manager):
    sid = manager.create("p1", title="Vlastní")["id"]
    manager.send(sid, "SLEEP")
    wait_for(lambda: manager.session(sid)["claudeSessionId"])
    claude_sid = manager.session(sid)["claudeSessionId"]
    with pytest.raises(AssistantError) as busy:
        manager.send(sid, "Další")
    assert busy.value.status == 409 and "odpovídá" in str(busy.value)
    stopped = manager.stop(sid)
    assert stopped["state"] == "idle" and stopped["title"] == "Vlastní"
    assert manager.running() == 0 and types(manager, sid)[-1] == "status"
    assert "error" not in types(manager, sid)
    manager.send(sid, "Pokračuj")
    idle_after_turn(manager, sid)
    assert f"resume={claude_sid}" in assistant_texts(manager, sid)[-1]


def test_process_limit(tmp_path):
    manager = make(tmp_path, limits=Limits(max_processes=3, tick_seconds=3600))
    try:
        ids = [manager.create("p1")["id"] for _ in range(4)]
        for sid in ids[:3]:
            manager.send(sid, "ahoj")
        for sid in ids[:3]:
            idle_after_turn(manager, sid)
        with pytest.raises(AssistantError) as full:
            manager.send(ids[3], "ahoj")
        assert full.value.status == 409 and "nejvýš 3" in str(full.value)
        manager.stop(ids[0])
        manager.send(ids[3], "ahoj")
        idle_after_turn(manager, ids[3])
    finally:
        manager.close_all()
    assert manager.running() == 0


def test_idle_timeout_ends_process_and_next_message_resumes(tmp_path):
    clock = Clock()
    manager = make(tmp_path, clock=clock)
    try:
        sid = manager.create("p1")["id"]
        manager.send(sid, "ahoj")
        idle_after_turn(manager, sid)
        claude_sid = manager.session(sid)["claudeSessionId"]
        clock.now += 60
        assert manager.sweep() == 0 and manager.running() == 1
        clock.now += 15 * 60
        assert manager.sweep() == 1
        wait_for(lambda: manager.running() == 0)
        assert "error" not in types(manager, sid)
        manager.send(sid, "znovu")
        idle_after_turn(manager, sid, 2)
        assert f"resume={claude_sid}" in assistant_texts(manager, sid)[-1]
    finally:
        manager.close_all()


def test_turn_timeout_kills_and_reports_error(tmp_path):
    clock = Clock()
    manager = make(tmp_path, clock=clock)
    try:
        sid = manager.create("p1")["id"]
        manager.send(sid, "SLEEP")
        wait_for(lambda: "status" in types(manager, sid))
        clock.now += 30 * 60 + 1
        assert manager.sweep() == 1
        events = manager.events(sid)[0]
        assert events[-2]["type"] == "error" and "30 minut" in events[-2]["message"]
        assert events[-1] == {**events[-1], "type": "status", "state": "idle"}
        assert manager.session(sid)["state"] == "idle" and manager.running() == 0
    finally:
        manager.close_all()


def test_process_death_mid_turn_reports_error(manager):
    sid = manager.create("p1")["id"]
    manager.send(sid, "DIE")
    wait_for(lambda: "error" in types(manager, sid))
    events = manager.events(sid)[0]
    error = next(event for event in events if event["type"] == "error")
    assert "uprostřed tahu" in error["message"] and "fake cli died" in error["message"]
    wait_for(lambda: types(manager, sid)[-1] == "status")
    assert manager.session(sid)["state"] == "idle"


def test_close_marks_closed_and_hides_session(manager):
    sid = manager.create("p1")["id"]
    manager.send(sid, "ahoj")
    idle_after_turn(manager, sid)
    closed = manager.close(sid)
    assert closed["state"] == "closed" and manager.running() == 0
    events, is_closed = manager.events(sid)
    assert is_closed and events[-1]["state"] == "closed"
    assert manager.sessions("p1") == []
    with pytest.raises(AssistantError):
        manager.send(sid, "ještě")


def test_errors_for_unknown_session_missing_cli_and_bad_input(tmp_path):
    manager = make(tmp_path, which=lambda name: None)
    with pytest.raises(SessionNotFound):
        manager.send("missing", "ahoj")
    with pytest.raises(AssistantError):
        manager.create("p1", model="haiku")
    with pytest.raises(ValueError):
        manager.create("nope")
    sid = manager.create("p1")["id"]
    with pytest.raises(ValueError):
        manager.send(sid, "ahoj", {"environment": "desktop"})
    with pytest.raises(AssistantUnavailable) as missing:
        manager.send(sid, "ahoj")
    assert missing.value.status == 503
    assert manager.status()["available"] is False
    assert manager.transcript(sid) == []


def test_placeholder_titles_take_first_message(manager):
    fresh = manager.create("p1")["id"]
    legacy = manager.create("p1", title="Nová session")["id"]
    for sid in (fresh, legacy):
        assert manager.session(sid)["title"] in ("Nový úkol", "Nová session")
        manager.send(sid, "Navrhni export plátna")
        idle_after_turn(manager, sid)
        assert manager.session(sid)["title"] == "Navrhni export plátna"


def test_rename_validates_and_survives_first_message(manager):
    sid = manager.create("p1")["id"]
    renamed = manager.rename(sid, "  Oprava mapy  ")
    assert renamed["title"] == "Oprava mapy" and renamed["lastSeq"] == 0
    for bad in ("", "   ", "x" * 81, "a\nb", None, 5):
        with pytest.raises(ValueError):
            manager.rename(sid, bad)
    assert manager.rename(sid, "x" * 80)["title"] == "x" * 80
    manager.rename(sid, "Ruční název")
    manager.send(sid, "první zpráva")
    idle_after_turn(manager, sid)
    assert manager.session(sid)["title"] == "Ruční název"
    with pytest.raises(SessionNotFound):
        manager.rename("missing", "Název")
    manager.close(sid)
    with pytest.raises(AssistantError) as closed:
        manager.rename(sid, "Jiný")
    assert closed.value.status == 409
