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


@pytest.fixture
def journal(monkeypatch):
    """Deník chyb zachycený na frontě: `records` = submit, `resolved` = resolve (pořadí volání)."""
    from backend.app import error_log

    calls = SimpleNamespace(records=[], resolved=[])
    monkeypatch.setattr(error_log, "submit", lambda source, kind, message, **kw: calls.records.append(
        {"source": source, "kind": kind, "message": message, **kw}))
    monkeypatch.setattr(error_log, "resolve", lambda **kw: calls.resolved.append(kw))
    return calls


def test_failed_batch_and_its_tool_failures_land_in_the_error_journal(heart_env, journal, monkeypatch, tmp_path):
    env = heart_env
    steps = [{"t": 0, "kind": "tool", "text": "Bash: python opora_heart.py brief"},
             {"t": 60000, "kind": "result", "text": 'Exit code 1 {"error": "x", "code": "server_unreachable"}'}]
    monkeypatch.setattr(batch, "run", lambda spec, runner, clock: {
        "at": "2026-11-13T01:00:00Z", "status": "timeout", "durationMs": 60500, "error": "vypršelo", "steps": steps})
    env.heart._add("p1", "draft", {"type": "commits", "log": []}, 1000.0)
    env.driver.tick()
    drain(env)
    batch_row, tool_row = journal.records
    assert (batch_row["source"], batch_row["kind"], batch_row["subject"], batch_row["project"]) == (
        "heart", "timeout", "2026-11-13T01:00:00Z", "p1")
    assert batch_row["cause"] == "vypršelo" and "explain?project=p1" in batch_row["lever"]
    assert (tool_row["kind"], tool_row["subject"]) == ("timeout", "2026-11-13T01:00:00Z")
    assert "opora_heart.py brief" in tool_row["message"]
    # další dávka ok uzavře záznamy předchozí dávky (subject = její `at` z deníku dávek)
    (tmp_path / batch.JOURNAL).write_text('{"at": "2026-11-13T01:00:00Z", "status": "timeout"}\n', encoding="utf-8")
    monkeypatch.setattr(batch, "run", lambda spec, runner, clock: {"at": "2026-11-13T02:00:00Z", "status": "ok"})
    env.clock[0] += 60
    env.heart._add("p1", "draft", {"type": "commits", "log": ["b"]}, env.clock[0])
    env.driver.tick()
    drain(env)
    assert {"source": "heart", "project": "p1", "subject": "2026-11-13T01:00:00Z"} in journal.resolved
    assert len(journal.records) == 2


def test_rate_limit_sleep_and_hour_cap_are_blocked_warnings_with_until(heart_env, journal):
    env = heart_env
    env.heart._add("p1", "draft", {"type": "commits", "status": "rate_limited"}, 1000.0)
    env.driver.tick()
    drain(env)
    [sleep] = journal.records
    assert (sleep["kind"], sleep["severity"], sleep["subject"]) == ("blocked", "warn", "rate_limit")
    assert sleep["data"]["until"] == "1970-01-01T00:31:40Z"  # 1000 s + 900 s spánku
    journal.records.clear()
    env.heart.sleeping_until = 0.0
    env.clock[0] += 3601
    _, vid = seed.ensure_active(env.db)
    graph = copy.deepcopy(workflows.get_version(env.db, vid)["graph"])
    next(n for n in graph["nodes"] if n["id"] == "srdce")["params"]["per_hour"] = 1
    draft = workflows.create_draft(env.db, env.driver.workflow_id, graph)
    workflows.set_candidate(env.db, draft["id"])
    workflows.activate(env.db, draft["id"])
    env.heart.pending.clear()
    env.heart._add("p1", "draft", {"type": "commits", "log": []}, env.clock[0])
    env.driver.tick()
    drain(env)
    [cap] = journal.records
    assert (cap["source"], cap["kind"], cap["subject"], cap["severity"]) == ("heart", "blocked", "hour_cap", "warn")
    assert cap["data"]["until"] and "per_hour" in cap["lever"]


def test_failed_run_start_is_recorded_with_project(heart_env, journal, monkeypatch):
    from backend.flow import interpreter

    env = heart_env
    monkeypatch.setattr(interpreter, "start_run", lambda *a, **k: (_ for _ in ()).throw(ValueError("vadná verze")))
    env.heart._add("p1", "draft", {"type": "commits", "log": []}, 1000.0)
    assert env.driver.tick() == []
    [row] = journal.records
    assert (row["source"], row["kind"], row["project"], row["subject"]) == ("heart", "exception", "p1", "run")
    assert "vadná verze" in row["cause"]


def test_missing_claude_is_recorded(heart_env, journal):
    env = heart_env
    env.heart.find = lambda: None
    env.heart._add("p1", "draft", {"type": "commits", "log": []}, 1000.0)
    env.driver.tick()
    drain(env)
    [row] = journal.records
    assert (row["source"], row["kind"], row["project"], row["subject"]) == ("heart", "exception", "p1", "claude")


def test_batch_timeout_reaches_the_real_error_journal(tmp_path):
    """Bez podvrženého submit: dnešní timeout `brief` (§6 M2) je řádek deníku s projektem, dávkou a pákou."""
    import sqlite3

    from backend.app import error_log, errors
    from backend.flow.catalogs.heart import nodes
    from database.schema.project_schema import REGISTRY_SCHEMA

    db = sqlite3.connect(tmp_path / "registry.sqlite")
    db.executescript(REGISTRY_SCHEMA)
    db.close()
    errors.configure(tmp_path)
    try:
        nodes._report_batch(tmp_path, "p1", "draft", {
            "at": "2026-11-13T01:00:00Z", "status": "timeout", "durationMs": 60000, "error": "vypršelo",
            "steps": [{"t": 0, "kind": "tool", "text": "Bash: python opora_heart.py brief"},
                      {"t": 60000, "kind": "result", "text": 'Exit code 1 {"code": "server_unreachable"}'}]})
        error_log.drain()
        found = {(r["kind"], r["subject"], r["project"]) for r in errors.read(project="p1")}
        assert found == {("timeout", "2026-11-13T01:00:00Z", "p1")}  # dávka i nástroj: jiná zpráva, stejný druh
        assert len(errors.read(project="p1")) == 2 and all(r["lever"] for r in errors.read(project="p1"))
    finally:
        errors.configure(None)
