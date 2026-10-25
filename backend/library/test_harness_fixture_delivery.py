"""The existing role worker delivers fixture facts without accepting the task."""
import json

from backend.editor.agent_memory.desktop_v3_state import default_state
from backend.library.harness_memory import HarnessMemory
from backend.library.test_harness_fixture_memory import insert, native
from backend.library.test_harness_fixture_memory import service as service  # noqa: PLC0414
from backend.library.test_harness_memory import Memory
from database.repositories import harness_fixture_memory as fixtures
from database.repositories import harness_memory as deliveries


def queued(service):
    db = service.db_for("draft")
    q, r = native()
    state = default_state()
    state["nodes"][q["nodeId"]] = {"phase": "discover", "criteria": [], "steps": [], "agentRole": "role-backend"}
    with db:
        insert(db, q, r)
        db.execute("INSERT OR REPLACE INTO desktop_v3_state VALUES(?,?,1,?,'now')",
                   ("draft", "draft", json.dumps(state)))
        assert fixtures.enqueue(db, "draft", "draft", q["id"])
    return db, q, r


class TaggedMemory(Memory):
    def write(self, role, uri, text, tags):
        self.tags = tags
        return super().write(role, uri, text, tags)


def test_fixture_delivery_uses_role_retry_and_separate_tag_without_task_success(service):
    db, q, _ = queued(service)
    memory, clock = TaggedMemory(), [1000]
    memory.available = False
    worker = HarnessMemory(service, memory, clock=lambda: clock[0])
    assert worker.run_once() == ["retry"]
    memory.available = True
    clock[0] += 60
    assert worker.run_once() == ["submitted"]
    assert memory.calls[0] == memory.calls[1]
    assert "kind=harness-fixture" in memory.tags and "kind=harness-outcome" not in memory.tags
    assert memory.calls[0][1]["productionOutcome"] == "unknown"
    assert worker.run_once() == []
    assert db.execute("SELECT COUNT(*) FROM harness_learning_outcomes").fetchone()[0] == 0
    # A fixture-memory fact must not count as an earlier accepted-task success to withdraw.
    with db:
        deliveries.enqueue(db, ("draft", "draft", q["executionId"]), 900, "unknown", "now")
    assert db.execute("SELECT COUNT(*) FROM harness_memory_deliveries").fetchone()[0] == 1


def test_changed_native_source_is_superseded_before_network_delivery(service):
    db, q, r = queued(service)
    r["authorityCurrentAtCompletion"] = False
    with db:
        db.execute("UPDATE opora_verification_reports SET record=? WHERE verification_id=?", (json.dumps(r), q["id"]))
    memory = TaggedMemory()
    assert HarnessMemory(service, memory).run_once() == ["superseded"]
    assert memory.calls == []
    assert deliveries.status(db, "draft", "draft")["items"][0]["state"] == "superseded"
