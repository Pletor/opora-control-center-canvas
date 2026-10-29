"""Supervisor srdce s falešným časem a procesem: buzení, okno 20 s, jedna dávka na projekt, strop a spánek."""
import json

import pytest

from backend.brain_opora.determinism import gate, gate_setting
from backend.brain_opora.heart import batch, supervisor
from backend.brain_opora.heart.process import Outcome
from backend.canvas.canvas_service import CanvasService

OK = {"is_error": False, "session_id": "11111111-1111-1111-1111-111111111111", "total_cost_usd": 0.01,
      "num_turns": 3, "usage": {"input_tokens": 100}, "modelUsage": {"claude-haiku-4-5": {"costUSD": 0.01}}}
LIMITED = {"is_error": True, "result": "You've hit your session limit"}


class Clock:
    def __init__(self, now=1_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


class Runner:
    def __init__(self):
        self.calls, self.result = [], OK

    def __call__(self, line, *, cwd, env, stdin_text, timeout):
        self.calls.append(stdin_text)
        return Outcome(0, json.dumps(self.result), "")


@pytest.fixture
def setup(tmp_path):
    service = CanvasService(tmp_path / "data")
    service.db_for("draft")
    gate_setting.write(service, {"project": "draft", "enabled": True})
    clock, runner, held = Clock(), Runner(), []
    heart = supervisor.HeartSupervisor(service, base_url="http://127.0.0.1:9", runner=runner, clock=clock,
                                       spawn=lambda fn: fn(), find=lambda: "claude")
    yield service, heart, clock, runner, held
    service.close()


def ask(service, body):
    session = gate.authenticate(service, gate.open_session(
        service, {"project": "draft", "workspace": "draft", "worker": {"name": "dev"}})["token"])
    return gate.create_request(service, session, {"kind": "ask", "body": body})


def test_enabled_only_on_loopback_and_not_off():
    assert supervisor.enabled({}) is True
    assert supervisor.enabled({"OPORA_HEART": "off"}) is False
    assert supervisor.enabled({"OPORA_CANVAS_HOST": "0.0.0.0"}) is False
    assert supervisor.enabled({"OPORA_CANVAS_HOST": "localhost"}) is True


def test_human_message_wakes_at_once_and_is_journaled(setup):
    service, heart, clock, runner, _ = setup
    assert heart.message("draft", "draft", "Chci web o dvou stránkách.") == 1
    assert heart.run_once() == ["draft"]
    assert "ZPRÁVA ČLOVĚKA: Chci web o dvou stránkách." in runner.calls[0] and "PROJEKT" in runner.calls[0]
    status = heart.status("draft")
    assert status["batches"][-1]["status"] == "ok" and status["session"]["batches"] == 1 and status["pending"] == 0
    assert status["running"] is False and status["sleeping"] is False


def test_worker_ticket_waits_for_the_window_and_own_escalation_does_not_wake(setup):
    service, heart, clock, runner, _ = setup
    assert heart.run_once() == []  # první průchod nastaví kurzor na konec outboxu
    ticket = ask(service, {"q": "Jakou barvu?"})
    assert heart.run_once() == [] and heart.status("draft")["pending"] == 1
    clock.now += supervisor.WINDOW + 1
    assert heart.run_once() == ["draft"]
    assert f"LÍSTEK {ticket['ticketId']} (ask)" in runner.calls[0] and "Jakou barvu?" in runner.calls[0]
    heart_session = gate.tokens.verify(service, heart.tokens[("draft", "draft")])
    gate.create_request(service, heart_session, {"kind": "ask", "body": {"text": "Pro člověka"}})
    clock.now += supervisor.WINDOW + 1
    assert heart.run_once() == [] and heart.status("draft")["pending"] == 0


def test_answered_ticket_is_dropped_before_the_batch(setup):
    service, heart, clock, runner, _ = setup
    heart.run_once()
    ticket = ask(service, {"q": "?"})
    heart.run_once()
    gate.answer(service, "draft", ticket["ticketId"], {"answer": "Ano"})
    clock.now += supervisor.WINDOW + 1
    assert heart.run_once() == ["draft"] and runner.calls == []  # nic k řešení, proces se nespustil


def test_one_batch_per_project_six_automatic_per_hour_and_human_bypasses(setup):
    service, heart, clock, runner, _ = setup
    parked = []
    heart.spawn = parked.append
    heart.message("draft", "draft", "první")
    assert heart.run_once() == ["draft"]
    heart.message("draft", "draft", "během dávky")
    assert heart.run_once() == []  # dávka projektu ještě běží
    parked.pop()()
    heart.spawn = lambda fn: fn()
    assert heart.run_once() == ["draft"] and "během dávky" in runner.calls[-1]
    for number in range(supervisor.PER_HOUR):  # automatické dávky (lístky) mají strop
        ask(service, {"q": f"otázka {number}"})
        heart.run_once()
        clock.now += supervisor.WINDOW + 1
        assert heart.run_once() == ["draft"]
    ask(service, {"q": "sedmá"})
    heart.run_once()
    clock.now += supervisor.WINDOW + 1
    assert heart.run_once() == [] and heart.next_allowed("draft", clock.now) > clock.now
    heart.message("draft", "draft", "zpráva člověka strop obchází")
    assert heart.run_once() == ["draft"] and "sedmá" in runner.calls[-1]
    ask(service, {"q": "osmá"})
    heart.run_once()
    clock.now += supervisor.WINDOW + 1
    assert heart.run_once() == []
    clock.now += supervisor.HOUR
    assert heart.run_once() == ["draft"]


def test_rate_limit_sleeps_and_keeps_inputs(setup):
    service, heart, clock, runner, _ = setup
    runner.result = LIMITED
    heart.message("draft", "draft", "Plán")
    heart.run_once()
    status = heart.status("draft")
    assert status["sleeping"] is True and status["pending"] == 1 and status["batches"][-1]["status"] == "rate_limited"
    runner.result = OK
    clock.now += supervisor.RATE_SLEEP - 1
    assert heart.run_once() == []
    clock.now += 2
    assert heart.run_once() == ["draft"] and "Plán" in runner.calls[-1]


def test_gate_off_and_missing_claude_drop_the_batch(setup):
    service, heart, clock, runner, _ = setup
    heart.find = lambda: None
    heart.message("draft", "draft", "x")
    heart.run_once()
    assert heart.status("draft")["error"] == "Claude Code nenalezen." and runner.calls == []
    heart.find = lambda: "claude"
    gate_setting.write(service, {"project": "draft", "enabled": False})
    heart.message("draft", "draft", "y")
    clock.now += 60
    heart.run_once()
    assert heart.status("draft")["error"] == "Brána projektu je vypnutá." and runner.calls == []
    assert batch.read_journal(heart.brain("draft")) == []
