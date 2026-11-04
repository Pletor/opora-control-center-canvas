"""Srdce ve zkouškách: skutečný `Heart` a `HeartDriver` nad skutečnou službou, uzly běží hned ve stejném vlákně."""
import json

import pytest

from backend.brain import seed as brain_seed
from backend.brain_opora.heart.process import Outcome
from backend.flow.catalogs.heart.driver import HeartDriver
from backend.flow.catalogs.heart.heart import Heart
from backend.flow.catalogs.heart.runtime import bind

OK = {"is_error": False, "session_id": "11111111-1111-1111-1111-111111111111", "total_cost_usd": 0.01,
      "num_turns": 3, "usage": {"input_tokens": 100}, "modelUsage": {"claude-haiku-4-5": {"costUSD": 0.01}}}


class Clock:
    def __init__(self, now=1_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


class Runner:
    def __init__(self):
        self.calls, self.result = [], OK

    def __call__(self, line, *, cwd, env, stdin_text, timeout, on_line=None):
        self.calls.append(stdin_text)
        return Outcome(0, json.dumps(self.result), "")


class Engine:
    """`run_once()` = průchod plánovače (`HeartDriver.tick`) a doběhnutí dávky; vrací projekty, kterým běh pustil.
    `hold = True` nechá dávku rozběhnutou (uzly čekají v `jobs`), `drain()` ji dokončí."""

    def __init__(self, service, heart):
        self.heart, self.jobs, self.hold = heart, [], False
        self.driver = HeartDriver(service, heart, spawn=self.jobs.append, heartbeat_seconds=None)
        self.driver.start()

    def drain(self):
        while self.jobs:
            self.jobs.pop(0)()

    def run_once(self):
        runs = self.driver.tick()
        projects = [self.driver.runs[run_id] for run_id in runs]
        if not self.hold:
            self.drain()
            self.driver._release()
        return projects


@pytest.fixture
def make_heart(monkeypatch, tmp_path):
    """`make_heart(service, clock, runner, **kwargs)` → `(heart, engine)`; vazba uzlů se po testu uvolní.
    Seed Brainu běží bez ponytailu (zkouška nesmí záviset na instalaci pluginů na stroji)."""
    monkeypatch.setattr(brain_seed, "PONYTAIL_CACHE", tmp_path / "bez-ponytailu")

    def make(service, clock, runner, **kwargs):
        heart = Heart(service, base_url="http://127.0.0.1:9", runner=runner, clock=clock, find=lambda: "claude",
                      git_spawn=lambda fn: fn(), **kwargs)
        return heart, Engine(service, heart)

    yield make
    bind(None)
