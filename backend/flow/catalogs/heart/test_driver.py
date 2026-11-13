"""Srdce v1 v enginu: seed, běh spouštěč → Jev → snímek → agent, stropy z parametrů uzlu a rozvrh."""
import copy
import threading
from types import SimpleNamespace

import pytest

from backend.brain import seed as brain_seed
from backend.brain_opora.decision import intake
from backend.brain_opora.determinism import gate_setting, snapshot
from backend.brain_opora.heart import batch
from backend.flow import workflows
from backend.flow.catalogs.heart import inputs, seed
from backend.flow.catalogs.heart.driver import HeartDriver
from backend.flow.catalogs.heart.heart import Heart
from backend.flow.catalogs.heart.state import enabled
from backend.flow.catalogs.heart.runtime import bind
from backend.flow.graph_check import graph_errors
from backend.flow.interpreter import get_run


@pytest.fixture
def heart_env(db, monkeypatch, tmp_path):
    specs, jobs, clock = [], [], [1000.0]
    monkeypatch.setattr(gate_setting, "is_on", lambda service, project: True)
    monkeypatch.setattr(inputs, "resolve", lambda service, project, items: [i for i in items if not i.get("gone")])
    monkeypatch.setattr(intake, "classify_pending",
                        lambda service, project, workspace, items, *, jev, now: [{**i, "jev": True} for i in items])
    monkeypatch.setattr(snapshot, "snapshot", lambda service, project, workspace, limit: f"SNÍMEK {project}")

    def run(spec, runner, clock_fn):
        specs.append(spec)
        return {"status": spec.inputs[0].get("status", "ok"), "costUsd": 0.05, "summary": "hotovo"}

    monkeypatch.setattr(batch, "run", run)
    monkeypatch.setattr(brain_seed, "PONYTAIL_CACHE", tmp_path / "bez-ponytailu")
    service = SimpleNamespace(db=db, registry_lock=threading.RLock(), root=tmp_path / "data")
    heart = Heart(service, base_url="http://127.0.0.1:1", clock=lambda: clock[0], find=lambda: "claude")
    for name, value in {"collect": lambda now: None, "_token": lambda p, w: "tok", "_source": lambda p, w: None,
                        "brain": lambda p: tmp_path, "_advance_before_batch": lambda p, w: None}.items():
        setattr(heart, name, value)
    driver = HeartDriver(service, heart, spawn=jobs.append, heartbeat_seconds=None)
    driver.start()
    yield SimpleNamespace(db=db, heart=heart, driver=driver, specs=specs, jobs=jobs, clock=clock)
    bind(None)


def drain(env):
    while env.jobs:
        env.jobs.pop(0)()


def test_seed_is_idempotent(db):
    assert graph_errors(seed.GRAPH) == []
    first, second = seed.ensure_active(db), seed.ensure_active(db)
    assert first == second
    assert [v["status"] for v in workflows.list_versions(db, first[0])] == ["active"]


def test_message_runs_the_whole_batch_and_frees_the_project(heart_env):
    env = heart_env
    status = env.heart.status("p1")
    assert status["enabled"] == enabled() and status["explain"] == "/api/pletor/heart/explain?project=p1&format=text"
    env.heart.message("p1", "draft", "Postav stránku", now=1000.0, record_intake=False)
    [run_id] = env.driver.tick()
    assert env.heart.running == {"p1"}
    assert get_run(env.db, run_id)["trigger"]["node_id"] == "zprava"
    drain(env)
    env.driver.tick()
    run = get_run(env.db, run_id)
    assert run["status"] == "succeeded"
    assert [row["node_id"] for row in run["node_runs"]] == ["zprava", "jev", "snimek", "srdce"]
    agent = run["node_runs"][-1]
    assert agent["model"] == "haiku" and agent["cost_usd"] == 0.05
    [spec] = env.specs
    assert spec.snapshot == "SNÍMEK p1" and spec.inputs[0]["jev"] is True
    assert (spec.model, spec.advisor_model, spec.subcommands) == ("haiku", "opus", None)
    assert spec.skills.prompt.startswith("# Srdce projektu OPORA")  # skilly srdce z aktivní verze v Brainu
    assert set(spec.skills.pins) == {"heart", "vyslech", "proces-na-platne"} and "vyslech" in spec.skills.modes
    assert env.heart.running == set() and not env.heart.starts.get("p1")  # zpráva člověka strop nepočítá


def test_caps_come_from_agent_params_not_constants(heart_env):
    env = heart_env
    _, vid = seed.ensure_active(env.db)
    graph = copy.deepcopy(workflows.get_version(env.db, vid)["graph"])
    agent = next(n for n in graph["nodes"] if n["id"] == "srdce")
    agent["params"]["per_hour"] = 1
    next(n for n in graph["nodes"] if n["id"] == "nastroj")["params"]["subcommands"] = ["plan", "done"]
    draft = workflows.create_draft(env.db, env.driver.workflow_id, graph)
    workflows.set_candidate(env.db, draft["id"])
    workflows.activate(env.db, draft["id"])
    env.heart._add("p1", "draft", {"type": "commits", "log": []}, 1000.0)
    assert len(env.driver.tick()) == 1
    env.heart._add("p1", "draft", {"type": "commits", "log": ["b"]}, 1000.0)
    assert env.driver.tick() == []  # běh projektu je otevřený (per_project 1)
    drain(env)
    assert env.driver.tick() == []  # dávka za hodinu vyčerpaná (per_hour 1)
    env.clock[0] += 3601
    assert len(env.driver.tick()) == 1
    assert env.specs[0].subcommands == ("plan", "done")


def test_empty_inputs_skip_the_agent_and_rate_limit_puts_inputs_back(heart_env):
    env = heart_env
    env.heart._add("p1", "draft", {"type": "commits", "gone": True}, 1000.0)
    [run_id] = env.driver.tick()
    drain(env)
    assert [row["node_id"] for row in get_run(env.db, run_id)["node_runs"]] == ["udalost"]
    env.heart._add("p1", "draft", {"type": "commits", "status": "rate_limited"}, 1000.0)
    env.driver.tick()
    drain(env)
    env.driver.tick()
    assert env.heart.sleeping_until == 1000.0 + 900
    assert [item for _, item, _ in env.heart.pending["p1"]] == [{"type": "commits", "status": "rate_limited"}]


def test_schedule_trigger_forces_full_card_scan(heart_env):
    env = heart_env
    env.heart.card_at["p1"] = 1000.0
    env.driver.tick()
    assert env.heart.card_at  # první průchod rozvrh nespustí
    env.clock[0] += 600
    env.driver.tick()
    assert env.heart.card_at == {} and env.heart.polled_at == float("-inf")


def test_failed_node_frees_the_project_with_error(heart_env, monkeypatch):
    env = heart_env
    monkeypatch.setattr(snapshot, "snapshot", lambda *args: (_ for _ in ()).throw(ValueError("rozbitý snímek")))
    env.heart._add("p1", "draft", {"type": "commits", "log": []}, 1000.0)
    [run_id] = env.driver.tick()
    drain(env)
    env.driver.tick()
    assert get_run(env.db, run_id)["status"] == "failed"
    assert env.heart.running == set() and "rozbitý snímek" in env.heart.errors["p1"]
