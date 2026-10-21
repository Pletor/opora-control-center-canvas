"""Conformance bridge (not a proof): randomized runs of the real execution service vs TLA+ invariants.

The driver issues seeded random claim / heartbeat / release / human force-release / result /
stale-credential / clock-advance steps against `ExecutionResults` on real SQLite with an
injected clock, records each step as an event and checks the log with the Python
re-implementations of OneActiveOwner, NoStaleEpochReceipt, OneReceiptPerExecution and
MonotonicEpoch (backend/canvas/opora_execution_conformance.py). The predicates are first
shown to reject hand-made bad logs, so a vacuous predicate cannot pass silently.
"""
import random
import time

import pytest

from backend.canvas.opora_execution_conformance import INVARIANTS, violations
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.opora_executions import OporaExecutions
from backend.canvas.test_opora_changesets import SCOPE, baseline
from backend.canvas.test_opora_changesets import service as service  # noqa: PLC0414
from backend.editor.agent_memory.card_leases import CardLeases
from database.schema.opora_execution_schema import SCHEMA

NODE, OWNERS, PAYLOADS = "a", ("agent:A", "agent:B"), ("P1", "P2")


class Clock:
    def __init__(self):
        self.value = time.time()

    def __call__(self):
        return self.value


def snapshot(service):
    """Card epoch and the executions whose lease would pass `lease_valid` right now."""
    authority = OporaExecutions(service)
    with authority.transaction(**SCOPE) as repo:
        row = repo.db.execute("SELECT epoch FROM opora_execution_epochs WHERE project_id=? AND workspace_id=?"
                              " AND node_id=?", (*SCOPE.values(), NODE)).fetchone()
        holders = []
        for record in repo.history(NODE):
            try:
                authority.lease_valid(repo, record)
                holders.append(record["executionId"])
            except ValueError:
                pass
    return (row[0] if row else 0), sorted(holders)


def step(service, results, clock, rng, runs, index):
    op = rng.choice(("claim", "claim", "heartbeat", "release", "force", "result", "result", "stale", "tick"))
    # Mostly the newest run (valid paths), sometimes an older one (stale credentials).
    run = (runs[-1] if rng.random() < 0.6 else rng.choice(runs)) if runs else None
    if op in {"heartbeat", "release", "result", "stale"} and run is None:
        op = "claim"
    event = {"step": index, "op": "result" if op == "stale" else op, "executionId": None, "epoch": None,
             "ok": False, "receiptId": None}
    event["epochBefore"], event["authorityBefore"] = snapshot(service)
    credentials = {} if run is None else {**SCOPE, "token": run["token"], "epoch": run["epoch"]}
    if run is not None:
        event["executionId"], event["epoch"] = run["executionId"], run["epoch"]
    try:
        if op == "claim":
            context = results.context(**SCOPE, node=NODE)
            record = results.claim({**SCOPE, "nodeId": NODE, "requestId": f"claim{index}", "ttlSeconds": rng.choice((60, 120)),
                                    "expectedAcceptedHead": context["acceptedHead"],
                                    "expectedContextVersion": context["contextVersion"]}, rng.choice(OWNERS))
            runs.append(record)
            event["executionId"], event["epoch"] = record["executionId"], record["epoch"]
        elif op == "heartbeat":
            results.heartbeat(run["executionId"], {**credentials, "ttlSeconds": 60})
        elif op == "release":
            results.release(run["executionId"], credentials)
        elif op == "force":
            CardLeases(service).apply({**SCOPE, "nodeId": NODE, "op": "release"}, actor="human")
        elif op == "tick":
            clock.value += rng.randint(1, 150)
        else:
            epoch = run["epoch"] + 1 if op == "stale" else run["epoch"]
            event["epoch"] = epoch
            receipt = results.submit(run["executionId"], {**credentials, "epoch": epoch,
                                                          "requestId": rng.choice(("r1", "r2")),
                                                          "result": {"summary": rng.choice(PAYLOADS)}})
            event["receiptId"] = receipt["receiptId"]
        event["ok"] = True
    except ValueError:
        pass
    event["epochAfter"], event["authorityAfter"] = snapshot(service)
    return event


@pytest.fixture
def driven(service, monkeypatch):
    service.db_for("draft").executescript(SCHEMA)
    baseline(service)
    clock = Clock()
    monkeypatch.setattr(time, "time", clock)
    return service, ExecutionResults(service), clock


@pytest.mark.parametrize("seed", range(6))
def test_random_lease_runs_conform_to_tla_invariants(driven, seed):
    service, results, clock = driven
    rng, runs = random.Random(seed), []
    log = [step(service, results, clock, rng, runs, index) for index in range(45)]
    assert violations(log) == {}, f"seed {seed}"
    # The scenario must actually exercise the guarded paths, otherwise conformance is vacuous.
    assert any(event["op"] == "claim" and event["ok"] for event in log)
    assert any(event["op"] == "result" and event["ok"] for event in log)
    assert any(event["op"] == "result" and not event["ok"] for event in log)


def event(**values):
    base = {"op": "result", "executionId": "x", "epoch": 1, "ok": True, "receiptId": "r",
            "epochBefore": 1, "epochAfter": 1, "authorityBefore": ["x"], "authorityAfter": []}
    return base | values


@pytest.mark.parametrize("name,log", [
    ("OneActiveOwner", [event(op="claim", authorityAfter=["x", "y"])]),
    ("NoStaleEpochReceipt", [event(epoch=1, epochBefore=2, authorityBefore=["y"])]),
    ("OneReceiptPerExecution", [event(), event(receiptId="r2", authorityBefore=["x"])]),
    ("MonotonicEpoch", [event(op="claim", epochBefore=2, epochAfter=1)]),
])
def test_predicates_reject_mutated_logs(name, log):
    assert name in violations(log)
    assert set(INVARIANTS) >= {name}
