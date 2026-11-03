"""Uzly mimo zámek registru: `running` s heartbeatem běží jinde, bez heartbeatu se naváže, pozdní hlášení se zahodí."""
from datetime import UTC, datetime, timedelta

from backend.flow.conftest import edge, node
from backend.flow.interpreter import advance, fail, finish, heartbeat, start_run
from backend.flow.node_types import NODE_TYPES, NodeType, Port
from backend.flow.workflows import create_draft, create_workflow

NOW = datetime(2026, 11, 3, 12, tzinfo=UTC)
REGISTRY = {**NODE_TYPES, "slow": NodeType("slow", 1, (Port("main", "in"), Port("main", "out")),
                                           lambda ctx: {"detach": True}, detached=True)}
GRAPH = {"nodes": [node("t", "trigger.manual"), node("s", "slow"), node("z", "debug.echo")],
         "edges": [edge("1", "t", "s"), edge("2", "s", "z")]}


def slow_run(db):
    wid = create_workflow(db, "heart", "Tok")["id"]
    vid = create_draft(db, wid, GRAPH, registry=REGISTRY)["id"]
    run = start_run(db, vid, {"payload": 1}, registry=REGISTRY, now=NOW)
    return run, next(row for row in run["node_runs"] if row["node_id"] == "s")


def test_detached_node_keeps_running_and_finish_continues_the_flow(db):
    run, slow = slow_run(db)
    assert run["status"] == "running" and slow["status"] == "running"
    assert advance(db, run["id"], REGISTRY, NOW + timedelta(minutes=4))["node_runs"][-1]["attempt"] == 1
    assert heartbeat(db, slow["id"], NOW + timedelta(minutes=4))
    done = finish(db, slow["id"], "main", {"hotovo": True}, {"model": "haiku", "cost_usd": 0.02},
                  REGISTRY, NOW + timedelta(minutes=8))
    assert done["status"] == "succeeded"
    rows = {row["node_id"]: row for row in done["node_runs"]}
    assert rows["s"]["model"] == "haiku" and rows["s"]["cost_usd"] == 0.02
    assert rows["z"]["output_ref"] == '{"hotovo": true}'
    assert finish(db, slow["id"], "main", None, registry=REGISTRY) is None


def test_silent_detached_node_is_retried_and_late_report_is_dropped(db):
    run, slow = slow_run(db)
    again = advance(db, run["id"], REGISTRY, NOW + timedelta(minutes=6))
    attempts = [row for row in again["node_runs"] if row["node_id"] == "s"]
    assert [(row["attempt"], row["status"]) for row in attempts] == [(1, "failed"), (2, "running")]
    assert attempts[1]["idempotency_key"] == slow["idempotency_key"]
    assert not heartbeat(db, slow["id"]) and fail(db, slow["id"], "pozdě") is None
    assert fail(db, attempts[1]["id"], "chyba")["status"] == "failed"
