"""Native evidence drives memory; transport failures, duplicate work and withdrawal stay honest."""
import json

import pytest

from backend.editor.agent_memory.desktop_v3_state import default_state
from backend.integrations.openviking_client import OpenVikingUnavailable
from backend.library.harness_memory import HarnessMemory
from backend.library.test_harness_learning import confirm, merged_link
from database.repositories import harness_memory as store


class Memory:
    def __init__(self):
        self.calls, self.available, self.on = [], True, True
        self.callback = lambda: None

    def enabled(self):
        return self.on

    def _role_client(self, role):
        assert role == "role-backend"
        return self

    def write(self, role, uri, text, tags):
        self.calls.append((uri, json.loads(text)))
        self.callback()
        if not self.available:
            raise OpenVikingUnavailable("simulated lost response; credentials must not be logged")
        return {"tagsApplied": True}


def role(world):
    service, _, _, record = world
    db = service.db_for("draft")
    state = default_state()
    state["nodes"][record["nodeId"]] = {"phase": "discover", "criteria": [], "steps": [], "agentRole": "role-backend"}
    with db:
        db.execute("INSERT OR REPLACE INTO desktop_v3_state VALUES(?,?,1,?,'now')",
                   ("draft", "draft", json.dumps(state)))


def closed(world):
    role(world)
    merged_link(world)
    confirm(world)


def jobs(world):
    return store.status(world[0].db_for("draft"), "draft", "draft")["items"]


def test_only_native_attributable_closure_enqueues_and_metadata_never_contains_content(learning_run):
    assert jobs(learning_run) == []
    closed(learning_run)
    service, _, _, record = learning_run
    rows = service.db_for("draft").execute("SELECT payload FROM harness_memory_deliveries").fetchall()
    assert len(rows) == 1
    payload = json.loads(rows[0][0])
    assert payload["outcome"] == "pass" and payload["executionId"] == record["executionId"]
    assert "content" not in payload["resource"] and "requires" not in payload["resource"]
    assert payload["meaning"].startswith("Historical selected-kit association")
    assert len(rows[0][0]) < 12000


def test_delivery_is_outside_sql_locks_and_lost_response_retries_the_identical_address(learning_run):
    closed(learning_run)
    service, _, _, _ = learning_run
    memory, clock = Memory(), [1000]
    memory.available = False
    memory.callback = lambda: pytest.fail("network ran inside source transaction") if service.db_for("draft").in_transaction else None
    worker = HarnessMemory(service, memory, clock=lambda: clock[0])
    assert worker.run_once() == ["retry"]
    assert jobs(learning_run)[0]["error"] == "memory-write-unavailable"
    assert "credentials" not in json.dumps(jobs(learning_run))
    memory.available = True
    assert worker.run_once() == []
    clock[0] += 60
    assert HarnessMemory(service, memory, clock=lambda: clock[0]).run_once() == ["submitted"]
    assert memory.calls[0] == memory.calls[1], "retry rewrites the identical immutable fact"
    assert worker.run_once() == []
    assert jobs(learning_run)[0]["attempts"] == 2


def test_reopen_withdrawal_has_another_address_and_never_overwrites_historical_success(learning_run):
    closed(learning_run)
    memory = Memory()
    worker = HarnessMemory(learning_run[0], memory)
    assert worker.run_once() == ["submitted"]
    confirm(learning_run, now=False)
    assert worker.run_once() == ["submitted"]
    assert memory.calls[0][0] != memory.calls[1][0]
    assert [call[1]["outcome"] for call in memory.calls] == ["pass", "unknown"]
    assert all(job["state"] == "submitted" for job in jobs(learning_run))


def test_undelivered_old_success_is_superseded_and_missing_role_stays_explicit(learning_run):
    merged_link(learning_run)
    confirm(learning_run)
    memory = Memory()
    worker = HarnessMemory(learning_run[0], memory)
    assert worker.run_once() == ["waiting-role"]
    assert memory.calls == []
    role(learning_run)
    confirm(learning_run, now=False)
    assert worker.run_once() == ["submitted"]
    assert memory.calls[0][1]["outcome"] == "unknown"


def test_disabled_memory_and_shutdown_never_send_or_acknowledge_a_closing_write(learning_run):
    closed(learning_run)
    memory = Memory()
    worker = HarnessMemory(learning_run[0], memory)
    memory.on = False
    assert worker.run_once() == [] and jobs(learning_run)[0]["attempts"] == 0
    memory.on = True
    memory.callback = worker.close
    assert worker.run_once() == []
    assert jobs(learning_run)[0]["state"] == "working"
    assert HarnessMemory(learning_run[0], memory).run_once() == [], "lease prevents immediate duplicate delivery"


def test_queue_and_outcome_roll_back_with_the_source_event(learning_run):
    role(learning_run)
    merged_link(learning_run)
    service, _, _, record = learning_run
    db = service.db_for("draft")
    from backend.canvas.opora_card_events import closures
    with pytest.raises(RuntimeError), db:
        db.execute("BEGIN IMMEDIATE")
        closures(db, "draft", "draft", {"nodes": {}}, {"nodes": {record["nodeId"]: {"done": {"confirmed": True, "by": "human"}}}}, "human")
        assert jobs(learning_run)
        raise RuntimeError("rollback source transaction")
    assert jobs(learning_run) == []


def test_two_deliverers_cannot_claim_a_live_lease_and_late_ack_is_fenced(learning_run):
    closed(learning_run)
    service = learning_run[0]
    first, second, clock = Memory(), Memory(), [1000]
    other = HarnessMemory(service, second, clock=lambda: clock[0])
    def interleave():
        assert other.run_once() == [], "live lease prevents a duplicate request"
        clock[0] += 301
        assert other.run_once() == ["submitted"], "expired lease recovers after restart"
    first.callback = interleave
    assert HarnessMemory(service, first, clock=lambda: clock[0]).run_once() == ["lease-lost"]
    assert first.calls == second.calls, "late and recovered writes address the same immutable fact"
    assert jobs(learning_run)[0]["state"] == "submitted"


def test_delivery_preserves_an_unrelated_live_execution_context(learning_run, learning_plan):
    from backend.canvas.test_opora_execution_context import claimed
    from backend.canvas.test_opora_executions import credentials
    _, authority, _ = learning_plan
    other = claimed(learning_plan, node="b", request="other-card")
    closed(learning_run)
    assert HarnessMemory(learning_run[0], Memory()).run_once() == ["submitted"]
    heartbeat = authority.heartbeat(other["executionId"], {**credentials(other), "ttlSeconds": 60})
    assert heartbeat["assignmentDigest"] == other["assignmentDigest"]
