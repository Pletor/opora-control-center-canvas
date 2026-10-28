import threading
from datetime import UTC, datetime, timedelta

import pytest

from backend.project.architecture.journey_running import (
    JourneyRunning,
    JourneyRunUnknown,
    validate_progress,
    validate_start,
)
from backend.project.architecture.journey_runs import JourneyRunInvalid


class Clock:
    def __init__(self):
        self.now = 0.0
        self.base = datetime(2026, 10, 28, 10, 0, tzinfo=UTC)

    def monotonic(self):
        return self.now

    def wall(self):
        return self.base + timedelta(seconds=self.now)


def make(limit=256):
    clock = Clock()
    return JourneyRunning(monotonic=clock.monotonic, wall=clock.wall, limit=limit), clock


def test_start_progress_and_running_view():
    running, clock = make()
    started = running.start("p1", "web", "kampan")
    assert started["startedAt"] == "2026-10-28T10:00:00Z" and len(started["runId"]) == 32
    assert running.running("p1") == {("web", "kampan"): {"runId": started["runId"], "at": "2026-10-28T10:00:00Z", "segment": None}}
    clock.now = 5
    running.progress(started["runId"], {"from": "s1", "to": "s2"})
    assert running.running("p1")[("web", "kampan")] == {"runId": started["runId"], "at": "2026-10-28T10:00:05Z",
                                                        "segment": {"from": "s1", "to": "s2"}}
    running.progress(started["runId"], {"from": "s1", "to": "s2", "ok": True})
    assert running.running("p1")[("web", "kampan")]["segment"]["ok"] is True
    assert running.running("p2") == {}


def test_ttl_runs_from_the_last_heartbeat():
    running, clock = make()
    run_id = running.start("p1", "web", "kampan")["runId"]
    clock.now = 100
    running.progress(run_id, {"from": "s1", "to": "s2"})
    clock.now = 220
    assert ("web", "kampan") in running.running("p1")
    clock.now = 220.5
    assert running.running("p1") == {}
    with pytest.raises(JourneyRunUnknown):
        running.progress(run_id, {"from": "s1", "to": "s2"})


def test_new_start_replaces_the_run_and_finish_clears_it():
    running, _ = make()
    first = running.start("p1", "web", "kampan")["runId"]
    second = running.start("p1", "web", "kampan")["runId"]
    assert running.running("p1")[("web", "kampan")]["runId"] == second
    with pytest.raises(JourneyRunUnknown):
        running.progress(first, {"from": "s1", "to": "s2"})
    running.finish("p1", "web", "kampan")
    assert running.running("p1") == {}
    running.finish("p1", "web", "kampan")  # bez běhu nic


def test_limit_drops_the_oldest_heartbeat():
    running, clock = make(limit=2)
    a = running.start("p1", "web", "a")["runId"]
    clock.now = 1
    running.start("p1", "web", "b")
    clock.now = 2
    running.progress(a, {"from": "s1", "to": "s2"})
    running.start("p1", "web", "c")
    assert set(running.running("p1")) == {("web", "a"), ("web", "c")}


def test_concurrent_heartbeats_are_safe():
    running, _ = make()
    ids = [running.start("p1", "web", f"j{index}")["runId"] for index in range(8)]
    threads = [threading.Thread(target=lambda run_id=run_id: [running.progress(run_id, {"from": "s1", "to": "s2"}) for _ in range(200)])
               for run_id in ids]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(running.running("p1")) == 8


def test_body_validation():
    assert validate_start({"project": "p1", "journeyId": "kampan"}) == ("p1", "kampan", None)
    assert validate_start({"project": "p1", "journeyId": "kampan", "applicationId": "web"}) == ("p1", "kampan", "web")
    assert validate_progress({"segment": {"from": "s1", "to": "s2"}, "ok": False}) == {"from": "s1", "to": "s2", "ok": False}
    for bad in ([], {"project": "p1"}, {"project": "p1", "journeyId": ""}, {"project": "p1", "journeyId": "j", "x": 1}):
        with pytest.raises(JourneyRunInvalid):
            validate_start(bad)
    for bad in ({}, {"segment": "s1"}, {"segment": {"from": "s1"}}, {"segment": {"from": "s1", "to": "s2"}, "ok": "ano"},
                {"segment": {"from": "s1", "to": "s2", "x": 1}}):
        with pytest.raises(JourneyRunInvalid):
            validate_progress(bad)
