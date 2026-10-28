"""Strážce práce: propadlý nárok, běh bez zprávy a zaseknutý krok; falešný čas, skutečný claim."""
import time
from datetime import UTC, datetime

from backend.canvas.opora_events import stamp
from backend.canvas.strazci import guard_prace
from backend.canvas.strazci.registry import GuardContext
from backend.canvas.test_opora_executions import claim
from backend.canvas.test_opora_lease_events import no_pull_module, planned  # noqa: F401
from backend.canvas.test_opora_changesets import service as service  # noqa: PLC0414

NOW = 1_800_000_000.0


def iso(seconds):
    return stamp(datetime.fromtimestamp(seconds, UTC))


def lease(expires=NOW + 600, run=True, messages=(NOW - 60,), step=None, deadline=None, state="running"):
    execution = {"executionId": "x1", "state": state, "deadline": deadline, "messages": list(messages),
                 "step": step} if run else None
    return {"workspaceId": "draft", "nodeId": "a", "owner": "agent:w", "expiresAt": expires, "execution": execution}


def rules(items, now=NOW):
    return [(item["rule"], item["key"]) for item in guard_prace.evaluate(items, now)]


def test_healthy_run_has_no_findings():
    assert rules([lease()]) == []


def test_expired_lease_is_reported_alone():
    found = rules([lease(expires=NOW - 1, messages=(NOW - 3600,))])
    assert found == [("work.lease-expired", "work:lease-expired:draft:a:x1")]
    assert rules([lease(expires=NOW - 1, run=False)]) == [("work.lease-expired", "work:lease-expired:draft:a:agent:w")]


def test_budget_deadline_also_expires_the_lease():
    assert rules([lease(deadline=NOW - 5)])[0][0] == "work.lease-expired"


def test_silence_over_ten_minutes_is_reported():
    assert rules([lease(messages=(NOW - 599,))]) == []
    [item] = guard_prace.evaluate([lease(messages=(NOW - 601, NOW - 900))], NOW)
    assert item["rule"] == "work.no-heartbeat" and item["executionId"] == "x1" and item["data"] == {"silentMinutes": 10}


def test_step_running_over_thirty_minutes_is_reported():
    step = {"kind": "step.started", "stepId": "s1", "at": iso(NOW - 1801)}
    assert ("work.step-stalled", "work:step-stalled:x1:s1") in rules([lease(step=step)])
    assert rules([lease(step={**step, "at": iso(NOW - 1799)})]) == []


def test_finished_run_with_live_lease_is_not_judged():
    assert rules([lease(messages=(NOW - 7200,), state="released")]) == []


def test_real_claim_reads_lease_messages_and_expires(planned, service):  # noqa: F811
    record = claim(planned)
    ctx = lambda now: GuardContext(service, "draft", now)  # noqa: E731
    [item] = guard_prace.read_leases(service, "draft")
    assert item["execution"]["executionId"] == record["executionId"] and item["execution"]["state"] == "running"
    assert max(item["execution"]["messages"]) >= time.time() - 60
    assert guard_prace.run(ctx(time.time())) == []
    [expired] = guard_prace.run(ctx(record["expiresAt"] + 1))
    assert expired["rule"] == "work.lease-expired" and expired["executionId"] == record["executionId"]
    assert expired["nodeId"] == "a"
