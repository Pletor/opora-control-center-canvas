import threading

from backend.claude_code.assistant.errors import AssistantError, AssistantUnavailable, SessionNotFound
from backend.claude_code.assistant.watchdog import Limits, Watchdog, expired


def test_defaults_match_contract():
    limits = Limits()
    assert (limits.max_processes, limits.idle_seconds, limits.turn_seconds) == (3, 900, 1800)


def test_expired_splits_idle_and_overdue_turns():
    limits = Limits(idle_seconds=10, turn_seconds=20)
    lives = {"idle": (None, 0), "fresh": (None, 95), "long": (70, 99), "busy": (90, 99)}
    assert sorted(expired(lives, 100, limits)) == [("idle", False), ("long", True)]


def test_watchdog_ticks_until_stopped():
    ticks = threading.Event()
    dog = Watchdog(ticks.set, 0.01)
    dog.ensure()
    assert ticks.wait(5)
    dog.stop()


def test_errors_carry_http_status():
    assert (AssistantError("x").status, SessionNotFound("x").status, AssistantUnavailable("x").status) == (409, 404, 503)
    assert isinstance(SessionNotFound("x"), ValueError)
