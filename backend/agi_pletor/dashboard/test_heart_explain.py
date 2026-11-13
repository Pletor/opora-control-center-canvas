"""Průhled srdce: proč čeká (strop za hodinu), fronta, tok s časy uzlů, rozpad dávky a zarážky; text pro agenta."""
import json
import threading
from collections import deque
from types import SimpleNamespace

import pytest

from backend.agi_pletor.dashboard import heart_explain, heart_stops
from backend.app import slow_requests
from backend.brain_opora.heart import batch
from backend.flow.catalogs.heart.state import HeartState
from backend.flow.conftest import db  # noqa: F401 - fixture registru s tabulkami toků

NOW = 1_800_000_000.0
P = "a" * 32


@pytest.fixture
def heart(tmp_path, monkeypatch):
    monkeypatch.setattr(heart_stops.gate_setting, "is_on", lambda service, project: True)
    monkeypatch.setenv("OPORA_HEART", "on")
    monkeypatch.setenv("OPORA_CANVAS_HOST", "127.0.0.1")
    state = HeartState(object(), base_url="http://127.0.0.1:9", runner=lambda *a, **k: None, find=lambda: None,
                       clock=lambda: NOW)
    state.brain = lambda project: tmp_path
    entry = {"at": "2026-11-13T00:17:44Z", "status": "ok", "summary": "Kroky 2.13.", "durationMs": 100_000,
             "inputs": [{"type": "ticket", "ticketId": "gt_1"}], "steps": [
                 {"t": 1000, "kind": "tool", "text": "Bash: python opora_heart.py steps --node n"},
                 {"t": 81_000, "kind": "result", "text": 'Exit code 1 {"code": "server_unreachable"}'}]}
    (tmp_path / batch.JOURNAL).write_text(json.dumps(entry) + "\n", encoding="utf-8")
    return state


def service(db):  # noqa: F811
    db.execute("INSERT INTO flow_runs(id, workflow_version_id, trigger, status, created_at, updated_at) VALUES"
               "('r','v',?, 'running','2026-11-13T01:00:37+00:00','t')", (json.dumps({"payload": {"project": P}}),))
    db.execute("INSERT INTO flow_node_runs(id, run_id, node_id, attempt, status, idempotency_key, started_at, ended_at)"
               " VALUES('n1','r','snimek',1,'succeeded','k1','2026-11-13T01:00:37+00:00','2026-11-13T01:02:35+00:00')")
    return SimpleNamespace(db=db, registry_lock=threading.RLock())


def test_hour_cap_queue_pipeline_and_stops(heart, db):  # noqa: F811
    heart._add(P, "w", {"type": "ticket", "ticketId": "gt_2"}, NOW - 5)
    heart.starts[P] = deque([NOW - 3000 + i for i in range(6)])
    view = heart_explain.explain(service(db), heart, P, NOW)
    assert view["now"]["state"] == "hour_cap" and "Zpráva člověka strop obchází" in view["now"]["sentence"]
    assert [(i["type"], i["ref"], i["workspace"], i["dueInS"]) for i in view["queue"]] == [("ticket", "gt_2", "w", 0)]
    assert view["pipeline"][0]["nodes"][0] == {"node": "snimek", "label": "snímek projektu", "status": "succeeded",
                                              "ms": 118_000, "error": None}
    assert view["batches"][0]["phases"][0]["id"] == "opora_write"
    active = {item["id"] for item in view["stops"] if item["active"]}
    assert active == {"hour_cap", "lock", "timeout"}
    text = heart_explain.text(view)
    assert "TEĎ: Strop 6" in text and "! Zápisy srdce čekají na server" in text and "snímek projektu 118 s" in text
    assert text.splitlines()[-1].startswith("DENÍK CHYB: ")  # počet otevřených + odkaz na /api/pletor/errors


def test_idle_without_inputs(heart, db):  # noqa: F811
    view = heart_explain.explain(service(db), heart, P, NOW)
    assert view["now"]["state"] == "idle" and view["queue"] == []


def test_running_without_batch_names_the_open_node_and_message_text(heart, db):  # noqa: F811
    services = service(db)
    db.execute("UPDATE flow_node_runs SET status='running', ended_at=NULL")
    db.execute("UPDATE flow_runs SET status='running'")
    heart.running.add(P)
    heart._add(P, "w", {"type": "message", "text": "Čekají 2 žádosti\n o kroky"}, NOW)
    view = heart_explain.explain(services, heart, P, NOW)
    assert view["now"]["sentence"].startswith("Tok srdce stojí v uzlu „snímek projektu“")
    assert "heartbeat" in view["now"]["sentence"]
    assert view["queue"][0]["ref"] == "Čekají 2 žádosti o kroky"


def test_stops_follow_the_last_batch_not_history(heart, db, tmp_path):  # noqa: F811
    fast = {"at": "2026-11-13T01:40:19Z", "status": "ok", "durationMs": 85_000, "steps": [
        {"t": 1000, "kind": "tool", "text": "Bash: python opora_heart.py plan"},
        {"t": 7000, "kind": "result", "text": '{"ok": true}'}]}
    with (tmp_path / batch.JOURNAL).open("a", encoding="utf-8") as journal:
        journal.write(json.dumps(fast) + "\n")
    services = service(db)
    db.execute("UPDATE flow_node_runs SET ended_at='2026-11-13T01:00:48+00:00'")  # snímek 11 s
    db.execute("UPDATE flow_runs SET status='succeeded'")
    view = heart_explain.explain(services, heart, P, NOW)
    active = {item["id"] for item in view["stops"] if item["active"]}
    assert not active & {"lock", "timeout"}


def test_slow_server_requests_show_who_held_the_server(heart, db, monkeypatch):  # noqa: F811
    monkeypatch.setattr(slow_requests, "_RECENT", type(slow_requests._RECENT)(maxlen=5))
    slow_requests._RECENT.append({"at": NOW - 120, "method": "GET", "path": "/api/oporahub/agent-state",
                                  "project": P, "ms": 65_000, "status": 200})
    slow_requests._RECENT.append({"at": NOW - 7200, "method": "GET", "path": "/old", "project": P, "ms": 9000,
                                  "status": 200})
    view = heart_explain.explain(service(db), heart, P, NOW)
    assert [(i["path"], i["ms"]) for i in view["slow"]] == [("/api/oporahub/agent-state", 65_000)]
    assert "GET /api/oporahub/agent-state 65 s (200)" in heart_explain.text(view)
