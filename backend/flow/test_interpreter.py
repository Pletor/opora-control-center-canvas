import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from backend.flow.conftest import edge, node
from backend.flow.interpreter import advance, decide, get_run, start_run
from backend.flow.node_types import NODE_TYPES, NodeType, Port
from backend.flow.run_log import read_log
from backend.flow.stalls import list_stalls
from backend.flow.workflows import FlowConflict, create_draft, create_workflow

NOW = datetime(2026, 11, 3, 12, tzinfo=UTC)


def version(db, graph, registry=NODE_TYPES):
    wid = create_workflow(db, "heart", "Tok")["id"]
    return create_draft(db, wid, graph, registry=registry)["id"]


def by_node(run):
    return {row["node_id"]: row for row in run["node_runs"]}


APPROVAL = {"nodes": [node("t", "trigger.manual"), node("a", "approval.human", params={"timeout_seconds": 60}),
                      node("yes", "debug.echo"), node("no", "debug.echo"), node("late", "debug.echo")],
            "edges": [edge("1", "t", "a"), edge("2", "a", "yes", source_port="approved"),
                      edge("3", "a", "no", source_port="rejected"), edge("4", "a", "late", source_port="timeout")]}


def test_linear_flow_logs_every_change_and_pinned_output(db):
    graph = {"nodes": [node("t", "trigger.manual"), node("e", "debug.echo"),
                       node("p", "debug.echo", pinned_output={"pevně": True}), node("z", "debug.echo")],
             "edges": [edge("1", "t", "e"), edge("2", "e", "p"), edge("3", "p", "z")]}
    run = start_run(db, version(db, graph), {"payload": {"ahoj": 1}}, now=NOW)
    assert run["status"] == "succeeded"
    rows = by_node(run)
    assert rows["e"]["output_ref"] == '{"ahoj": 1}'
    assert rows["z"]["output_ref"] == '{"pevně": true}'
    assert all(row["attempt"] == 1 and row["idempotency_key"] for row in run["node_runs"])
    log = read_log(db, run["id"])
    assert [e["type"] for e in log][:3] == ["run.created", "node.queued", "run.status"]
    assert log[-1]["payload"] == {"status": "succeeded"}
    assert [e["seq"] for e in read_log(db, run["id"], after_seq=log[2]["seq"])] == [e["seq"] for e in log[3:]]
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE flow_log_events SET type='x'")


@pytest.mark.parametrize("decision, branch", [("approved", "yes"), ("rejected", "no")])
def test_approval_decision_picks_branch(db, decision, branch):
    run = start_run(db, version(db, APPROVAL), {"payload": "záměr"}, now=NOW)
    assert run["status"] == "waiting"
    waiting = by_node(run)["a"]
    assert waiting["waiting_for"] == "human"
    assert datetime.fromisoformat(waiting["deadline"]) == NOW + timedelta(seconds=60)
    done = decide(db, waiting["id"], decision, now=NOW)
    assert done["status"] == "succeeded"
    assert set(by_node(done)) == {"t", "a", branch}
    assert by_node(done)[branch]["output_ref"] == '"záměr"'
    assert decide(db, waiting["id"], decision, now=NOW)["node_runs"] == done["node_runs"]
    other = "rejected" if decision == "approved" else "approved"
    with pytest.raises(FlowConflict):
        decide(db, waiting["id"], other, now=NOW)


def test_approval_timeout_continues_timeout_branch(db):
    run = start_run(db, version(db, APPROVAL), now=NOW)
    assert advance(db, run["id"], now=NOW + timedelta(seconds=59))["status"] == "waiting"
    assert len(list_stalls(db, now=NOW + timedelta(seconds=61))) == 1
    done = advance(db, run["id"], now=NOW + timedelta(seconds=61))
    assert done["status"] == "succeeded"
    assert by_node(done)["a"]["output_port"] == "timeout"
    assert set(by_node(done)) == {"t", "a", "late"}
    assert list_stalls(db, now=NOW + timedelta(hours=1)) == []
    with pytest.raises(FlowConflict):
        decide(db, by_node(done)["a"]["id"], "approved", now=NOW)


def test_interrupted_run_resumes_unfinished_node_with_same_key(db):
    calls = []

    def flaky(ctx):
        calls.append((ctx["idempotency_key"], ctx["attempt"]))
        if len(calls) == 1:
            raise KeyboardInterrupt  # pád procesu uprostřed uzlu: řádek zůstane running
        return {"port": "main", "output": ctx["input"]}

    registry = {**NODE_TYPES, "flaky": NodeType("flaky", 1, (Port("main", "in"), Port("main", "out")), flaky)}
    graph = {"nodes": [node("t", "trigger.manual"), node("f", "flaky"), node("e", "debug.echo")],
             "edges": [edge("1", "t", "f"), edge("2", "f", "e")]}
    vid = version(db, graph, registry)
    with pytest.raises(KeyboardInterrupt):
        start_run(db, vid, {"payload": 7}, registry=registry, now=NOW)
    run_id = db.execute("SELECT id FROM flow_runs").fetchone()[0]
    assert db.execute("SELECT status FROM flow_node_runs WHERE node_id='f'").fetchone()[0] == "running"
    done = advance(db, run_id, registry=registry, now=NOW)
    assert done["status"] == "succeeded"
    attempts = [row for row in done["node_runs"] if row["node_id"] == "f"]
    assert [(r["attempt"], r["status"]) for r in attempts] == [(1, "failed"), (2, "succeeded")]
    assert calls[0][0] == calls[1][0] and [c[1] for c in calls] == [1, 2]
    assert by_node(done)["e"]["output_ref"] == "7"


def test_advance_is_idempotent_and_failure_fails_run(db):
    def boom(ctx):
        raise RuntimeError("rozbito")

    registry = {**NODE_TYPES, "boom": NodeType("boom", 1, (Port("main", "in"),), boom)}
    ok = start_run(db, version(db, {"nodes": [node("t", "trigger.manual"), node("e", "debug.echo")],
                                    "edges": [edge("1", "t", "e")]}), now=NOW)
    log_size = len(read_log(db, ok["id"]))
    assert advance(db, ok["id"], now=NOW)["node_runs"] == ok["node_runs"]
    assert len(read_log(db, ok["id"])) == log_size
    graph = {"nodes": [node("t", "trigger.manual"), node("b", "boom")], "edges": [edge("1", "t", "b")]}
    failed = start_run(db, version(db, graph, registry), registry=registry, now=NOW)
    assert failed["status"] == "failed" and by_node(failed)["b"]["error"] == "rozbito"


def test_sub_ports_are_config_not_steps(db):
    seen = {}

    def agent(ctx):
        seen.update(ctx["config"])
        return {"port": "main", "output": "ok"}

    registry = {**NODE_TYPES,
                "agent": NodeType("agent", 1, (Port("main", "in"), Port("main", "out"),
                                               Port("model", "in", "model", "one")), agent),
                "model": NodeType("model", 1, (Port("model", "out", "model"),), lambda ctx: pytest.fail("krok"))}
    graph = {"nodes": [node("t", "trigger.manual"), node("a", "agent"),
                       node("m", "model", params={"name": "haiku"})],
             "edges": [edge("1", "t", "a"), edge("2", "m", "a", "model", "model", "model")]}
    run = start_run(db, version(db, graph, registry), registry=registry, now=NOW)
    assert run["status"] == "succeeded" and set(by_node(run)) == {"t", "a"}
    assert seen == {"model": [{"node_id": "m", "type": "model", "params": {"name": "haiku"}, "port": "model"}]}
    assert get_run(db, run["id"])["trigger"]["node_id"] == "t"
