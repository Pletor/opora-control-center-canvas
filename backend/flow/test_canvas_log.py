"""Log pláten 2–4: událost jde do `flow_log_events`, jen chyba `*.failed` zapíše `canvas.failed` do outboxu (srdce)."""

import json
import sqlite3
import threading
from types import SimpleNamespace

import pytest

from backend.flow.canvas_log import log_canvas
from backend.flow.graph_check import FlowInvalid
from backend.flow.workflows import FlowNotFound
from database.schema.opora_event_schema import SCHEMA as EVENT_SCHEMA
from database.schema.opora_event_schema import ensure_process_columns


def make_service(db):
    db.execute("INSERT INTO projects(id,name) VALUES('p','P')")
    project = sqlite3.connect(":memory:", check_same_thread=False)
    project.executescript(EVENT_SCHEMA)
    ensure_process_columns(project)
    return SimpleNamespace(db=db, registry_lock=threading.RLock(), db_for=lambda pid: project,
                           lock_for=lambda pid: threading.RLock(),
                           project_hub=SimpleNamespace(settings=lambda pid: {"project": {"sourceKind": "git"}}))


def test_only_failures_reach_the_outbox(db):
    service = make_service(db)
    log_canvas(service, "p", 3, "plan.changed", {"x": 1}, "heart")
    done = log_canvas(service, "p", 4, "monitor.failed", {"check": "uptime"}, "worker")
    assert done == {"seq": 2, "canvas": 4, "kind": "monitor.failed"}
    rows = db.execute("SELECT type, canvas, payload FROM flow_log_events ORDER BY seq").fetchall()
    assert [(r["type"], r["canvas"], json.loads(r["payload"])) for r in rows] == [
        ("plan.changed", 3, {"x": 1, "project": "p", "author": "heart"}),
        ("monitor.failed", 4, {"check": "uptime", "project": "p", "author": "worker"})]
    events = service.db_for("p").execute("SELECT kind, workspace_id, actor_kind, data FROM opora_events").fetchall()
    assert [(e[0], e[1], e[2]) for e in events] == [("canvas.failed", "main", "agent")]
    assert json.loads(events[0][3]) == {"seq": 2, "canvas": 4, "kind": "monitor.failed", "payload": {"check": "uptime"}}


def test_read_canvas_returns_latest_events_of_one_project(db):
    from backend.flow.run_log import read_canvas

    service = make_service(db)
    for index in range(3):
        log_canvas(service, "p", 4, "outage.failed", {"i": index}, "monitor")
    log_canvas(service, "p", 3, "plan.changed", {}, "heart")
    events = read_canvas(db, 4, "p", limit=2)
    assert [event["payload"]["i"] for event in events] == [1, 2] and read_canvas(db, 4, "other") == []


def test_canvas_one_and_unknown_project_are_refused(db):
    service = make_service(db)
    with pytest.raises(FlowInvalid):
        log_canvas(service, "p", 1, "node.failed", {}, "human")
    with pytest.raises(FlowNotFound):
        log_canvas(service, "nikdo", 2, "intent.failed", {}, "human")
