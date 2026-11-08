"""Tah Pletora s falešným procesem: po limitu předplatného přepne účet claude-swap a tah jednou zopakuje."""
import json

import pytest

from backend.agi_pletor import session
from backend.brain_opora.heart.process import Outcome

LIMITED = {"type": "result", "session_id": "s1", "is_error": True, "result": "You've hit your session limit"}
OK = {"type": "result", "session_id": "s1", "is_error": False, "result": json.dumps({"reply": "Ano.", "actions": []})}


def runner_of(results, calls):
    def run(line, *, cwd, env, stdin_text, timeout, on_line=None):
        calls.append(stdin_text)
        return Outcome(0, json.dumps(results.pop(0)), "")
    return run


def test_limit_switches_account_and_retries_once(tmp_path):
    calls, switches = [], []
    reply, actions = session.turn(tmp_path, "Ahoj", runner=runner_of([LIMITED, OK], calls), find=lambda: "claude",
                                  switch=lambda: switches.append(1) or True)
    assert (reply, actions, len(calls), switches) == ("Ano.", [], 2, [1])


def test_limit_without_other_account_fails_after_one_run(tmp_path):
    calls = []
    with pytest.raises(RuntimeError, match="limit předplatného"):
        session.turn(tmp_path, "Ahoj", runner=runner_of([LIMITED, LIMITED], calls), find=lambda: "claude", switch=lambda: False)
    assert len(calls) == 1


def test_model_goes_to_command(tmp_path):
    lines = []

    def run(line, **kwargs):
        lines.append(line)
        return Outcome(0, json.dumps(OK), "")

    session.turn(tmp_path, "Ahoj", runner=run, find=lambda: "claude", model="haiku")
    assert lines[0][lines[0].index("--model") + 1] == "haiku"
    default = session.build_command("claude", "s", False)
    assert default[default.index("--model") + 1] == "sonnet"


def test_effort_only_when_set():
    assert "--effort" not in session.build_command("claude", "s", False)
    line = session.build_command("claude", "s", False, effort="high")
    assert line[line.index("--effort") + 1] == "high"
