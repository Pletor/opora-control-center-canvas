"""Plánovač na pozadí: háčky, vypršelé čekání a zařazené uzly posune, hotové a čekající v limitu nechá být."""
import threading
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from backend.flow.conftest import edge, node
from backend.flow.interpreter import get_run, start_run
from backend.flow.run_log import append
from backend.flow.scheduler import FlowScheduler, due_runs
from backend.flow.workflows import create_draft, create_workflow

NOW = datetime(2026, 11, 3, 12, tzinfo=UTC)
APPROVAL = {"nodes": [node("t", "trigger.manual"), node("a", "approval.human", params={"timeout_seconds": 60}),
                      node("late", "debug.echo")],
            "edges": [edge("1", "t", "a"), edge("2", "a", "late", source_port="timeout")]}


def test_due_runs_and_run_once_advance_expired_and_queued_runs(db):
    vid = create_draft(db, create_workflow(db, "heart", "Tok")["id"], APPROVAL)["id"]
    waiting = start_run(db, vid, {"payload": "x"}, now=NOW)["id"]
    stuck = start_run(db, vid, {"payload": "y"}, now=NOW)["id"]
    with db:  # pád mezi zápisy: zařazený uzel, který nikdo nevykonal
        append(db, stuck, "nr-stuck", "node.queued", {"node_id": "late", "attempt": 1, "idempotency_key": "k",
                                                      "input": "y"}, moment=NOW)
    assert due_runs(db, NOW) == [stuck]
    later = NOW + timedelta(seconds=61)
    assert due_runs(db, later) == sorted([waiting, stuck])
    ticks = []
    scheduler = FlowScheduler(SimpleNamespace(db=db, registry_lock=threading.RLock()),
                              [SimpleNamespace(start=lambda: None, tick=lambda: ticks.append(1))])
    assert scheduler.run_once(later) == sorted([waiting, stuck])
    assert ticks == [1] and get_run(db, waiting)["node_runs"][-1]["node_id"] == "late"
    assert due_runs(db, later) == []


def test_broken_hook_is_dropped_and_scheduler_starts(db):
    def broken():
        raise RuntimeError("seed selhal")

    scheduler = FlowScheduler(SimpleNamespace(db=db, registry_lock=threading.RLock()),
                              [SimpleNamespace(start=broken, tick=None)], tick=60)
    scheduler.start()
    try:
        assert scheduler.hooks == [] and scheduler.thread.is_alive()
    finally:
        scheduler.close()


def test_page_intent_run_is_skipped(db):
    """Záměr stránky se nespouští; i zbloudilý zařazený uzel jeho verze plánovač přeskočí."""
    db.execute("INSERT INTO projects(id,name) VALUES('p','P')")
    wid = create_workflow(db, "page_intent", "Záměr", project_id="p", owner_ref="opora:page:n1")["id"]
    graph = {"nodes": [node("in", "intent.entry"), node("ok", "intent.done")], "edges": [edge("1", "in", "ok")]}
    vid = create_draft(db, wid, graph)["id"]
    with db:
        append(db, "r", None, "run.created", {"workflow_version_id": vid, "trigger": {}}, moment=NOW)
        append(db, "r", "nr", "node.queued", {"node_id": "in", "attempt": 1, "idempotency_key": "k", "input": None},
               moment=NOW)
    assert due_runs(db, NOW) == []
