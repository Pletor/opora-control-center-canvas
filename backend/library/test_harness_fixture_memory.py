"""Native fixture facts share the durable queue, never task-success aggregates."""
import copy
import json

import pytest

from backend.canvas.canvas_service import now
from backend.canvas.opora_verification_validation import digest
from backend.canvas.test_opora_changesets import service as service  # noqa: PLC0414
from database.repositories import harness_fixture_memory as memory
from database.repositories import harness_memory as deliveries
from database.repositories.opora_verifications import Verifications


def native(outcome="passed"):
    binding = {"project": "draft", "workspace": "draft", "executionId": "exec-native", "nodeId": "a",
               "epoch": 1, "acceptedRevision": "a" * 40, "assignmentDigest": "b" * 64}
    origin = {"execution": dict(binding), "plan": {"id": "testing:plan", "digest": "c" * 64},
              "baseline": {"id": "scripts:base", "digest": "d" * 64},
              "candidate": {"id": "scripts:new", "digest": "e" * 64}, "problem": "problem:example",
              "image": "node@sha256:" + "f" * 64, "protocol": "harness.server-fixtures/1"}
    q = {"id": "verification-native", "domain": "harness-fixtures", **binding,
         "requestId": "harness-verifier-1", "requestDigest": digest(origin), "manifestDigest": digest([]),
         "verification": {"artifacts": []}, "origin": {"kind": "harness-server-verifier", **origin},
         "trust": "server-pending", "sourceBinding": "canvas-verified", "currentEligibility": False,
         "independentlyVerified": False, "plannedTrials": 2, "createdAt": now()}
    paired = {"complete": True, "cleanupComplete": True, "plannedTrials": 2, "observedTrials": 2,
              "improvements": 0, "regressions": int(outcome == "failed"), "unknownPairs": 0,
              "trials": [{"case": "case-one", "side": side, "order": index, "outcome": "fail" if outcome == "failed" and side == "candidate" else "pass",
                          "reason": "output-mismatch" if outcome == "failed" and side == "candidate" else "expected-output",
                          "exitCode": 0, "durationMs": 1, "outputDigest": "a" * 64}
                         for index, side in enumerate(("baseline", "candidate"), 1)]}
    body = {"outcome": outcome, "checkedClaims": ["fixture-output"] if outcome == "passed" else [],
            "summary": "Server-owned paired fixture rerun; no production or promotion claim.", "artifacts": [],
            "paired": paired, "authorityCurrentAtCompletion": True, "promotionAllowed": False}
    r = {**body, "requestId": q["requestId"], "reportDigest": digest({"request": q["requestDigest"], "report": body}),
         "manifestDigest": digest([]), "createdAt": now(), "trust": "server-observed",
         "independentlyVerified": True, "sourceBinding": "canvas-verified", "currentEligibility": False}
    return q, r


def insert(db, q, r):
    Verifications(db, q["project"], q["workspace"]).insert(q)
    if r is not None:
        db.execute("INSERT INTO opora_verification_reports VALUES(?,?,?,?,?,?)",
                   (q["id"], q["project"], q["workspace"], r["requestId"], r["reportDigest"], json.dumps(r)))


@pytest.fixture
def db(service):
    return service.db_for("draft")


@pytest.mark.parametrize("outcome", ["passed", "failed"])
def test_sanitized_fact_replay_and_real_event_without_task_credit(db, outcome):
    q, r = native(outcome)
    with db:
        insert(db, q, r)
        assert memory.enqueue(db, "draft", "draft", q["id"])
        assert not memory.enqueue(db, "draft", "draft", q["id"])
    with db:
        job = deliveries.claim(db, "draft", 100)
    payload = json.loads(job["payload"])
    assert memory.current(db, job)
    assert payload["outcome"] == outcome and payload["productionOutcome"] == "unknown"
    assert payload["promotionAllowed"] is False and payload["candidate"]["contentDigest"] == "e" * 64
    assert payload["at"] == r["createdAt"] and payload["reportDigest"] == r["reportDigest"]
    assert "native Harness fixture quarantine" in payload["meaning"]
    assert set(payload) == {"schema", "project", "workspace", "executionId", "nodeId", "problem", "candidate", "plan",
                            "baseline", "verificationId", "requestDigest", "reportDigest", "sourceEvent", "at", "outcome",
                            "productionOutcome", "promotionAllowed", "meaning"}
    event = db.execute("SELECT kind,node_id,execution_id FROM opora_events WHERE id=?", (payload["sourceEvent"],)).fetchone()
    assert tuple(event) == ("harness.fixture.observed", "a", "exec-native")
    assert db.execute("SELECT COUNT(*) FROM harness_memory_deliveries").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM harness_learning_outcomes").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM harness_learning_runs").fetchone()[0] == 0


def test_source_event_queue_rollback_together(db):
    q, r = native()
    before = db.execute("SELECT COUNT(*) FROM opora_events").fetchone()[0]
    with pytest.raises(RuntimeError), db:
        insert(db, q, r)
        assert memory.enqueue(db, "draft", "draft", q["id"])
        raise RuntimeError("rollback")
    assert db.execute("SELECT COUNT(*) FROM harness_memory_deliveries").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM opora_verification_requests").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM opora_events").fetchone()[0] == before
    with pytest.raises(ValueError, match="source transaction"):
        memory.enqueue(db, "draft", "draft", q["id"])


@pytest.mark.parametrize("side,path,value", [
    (0, ["trust"], "agent-reported"), (0, ["independentlyVerified"], 0),
    (0, ["sourceBinding"], "agent-reported"), (0, ["currentEligibility"], 0),
    (0, ["requestDigest"], "0" * 64), (0, ["origin", "candidate", "digest"], "0" * 64),
    (0, ["origin", "execution", "epoch"], 2), (0, ["origin", "execution", "epoch"], True),
    (1, ["trust"], "agent-reported"), (1, ["independentlyVerified"], 1),
    (1, ["paired", "complete"], 1), (1, ["paired", "cleanupComplete"], False),
    (1, ["authorityCurrentAtCompletion"], 1), (1, ["promotionAllowed"], 0),
    (1, ["reportDigest"], "0" * 64), (1, ["paired", "trials", 0, "outputDigest"], "0" * 64),
])
def test_forged_or_altered_native_records_never_enqueue(db, side, path, value):
    records = native()
    target = records[side]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with db:
        insert(db, *records)
        assert not memory.enqueue(db, "draft", "draft", records[0]["id"])
    assert db.execute("SELECT COUNT(*) FROM harness_memory_deliveries").fetchone()[0] == 0


def test_missing_pending_and_foreign_scope_are_not_memory_facts(db):
    q, _ = native()
    with db:
        insert(db, q, None)
        assert not memory.enqueue(db, "draft", "draft", q["id"])
        assert not memory.enqueue(db, "draft", "other", q["id"])
        assert not memory.enqueue(db, "other", "draft", q["id"])
        assert not memory.enqueue(db, "draft", "draft", "missing")


def queued(db):
    q, r = native()
    with db:
        insert(db, q, r)
        memory.enqueue(db, "draft", "draft", q["id"])
        return deliveries.claim(db, "draft", 100)


def test_outbox_pruning_keeps_fact_but_native_tampering_supersedes(db):
    job = queued(db)
    with db:
        db.execute("DELETE FROM opora_events")
    assert memory.current(db, job)
    with db:
        db.execute("UPDATE opora_verification_reports SET digest=?", ("0" * 64,))
    assert not memory.current(db, job)


@pytest.mark.parametrize("field,value", [("node", "foreign"), ("sourceEvent", 999), ("candidate", "foreign"), ("execution", "foreign"), ("scope", "foreign")])
def test_changed_queue_binding_is_not_current(db, field, value):
    job = queued(db)
    changed = copy.deepcopy(job)
    if field == "node":
        changed["node"] = value
    else:
        key = list(changed["key"])
        key[{"sourceEvent": 3, "candidate": 4, "execution": 2, "scope": 1}[field]] = value
        changed["key"] = tuple(key)
    assert not memory.current(db, changed)
    assert memory.current(db, job)


def test_altered_payload_or_native_scope_is_not_current(db):
    job = queued(db)
    changed = copy.deepcopy(job)
    payload = json.loads(changed["payload"])
    payload["productionOutcome"] = "pass"
    changed["payload"] = json.dumps(payload)
    assert not memory.current(db, changed)
    with db:
        db.execute("UPDATE opora_verification_requests SET workspace_id='foreign'")
    assert not memory.current(db, job)
