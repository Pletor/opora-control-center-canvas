"""Real SQLite claims/results retain authority across retries, expiry and legacy workers."""
import copy
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.test_opora_changesets import SCOPE, baseline, legacy_save, service  # noqa: F401
from backend.editor.agent_memory.card_leases import CardLeases
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from database.repositories.opora_executions import Executions
from database.schema.opora_execution_schema import SCHEMA


@pytest.fixture
def authority(service):
    service.db_for("draft").executescript(SCHEMA)
    baseline(service)
    return ExecutionResults(service)


def claim(authority, request="first", node="a"):
    context = authority.context(**SCOPE, node=node)
    return authority.claim({**SCOPE, "nodeId": node, "requestId": request, "ttlSeconds": 60,
                            "expectedAcceptedHead": context["acceptedHead"],
                            "expectedContextVersion": context["contextVersion"]}, "agent:worker")


def credentials(record):
    return {**SCOPE, "token": record["token"], "epoch": record["epoch"]}


def test_receipt_replay_has_no_state_effect_and_releases_lease(authority, service):
    record = claim(authority)
    before = DesktopV3State(service).read(**SCOPE)
    payload = {**credentials(record), "requestId": "result1", "result": {"summary": "Ready", "done": True}}
    receipt = authority.submit(record["executionId"], payload)
    assert "token" not in str(receipt)
    assert receipt == authority.submit(record["executionId"], payload)
    assert DesktopV3State(service).read(**SCOPE) == before
    assert service.db_for("draft").execute("SELECT COUNT(*) FROM card_leases").fetchone()[0] == 0
    with pytest.raises(ValueError, match="different content"):
        authority.submit(record["executionId"], {**payload, "result": {"summary": "Changed"}})
    with pytest.raises(ValueError, match="authoritative"):
        authority.submit(record["executionId"], {**payload, "requestId": "result2"})


def test_monotonic_epoch_and_delayed_writer_cannot_release_new_lease(authority):
    first = claim(authority)
    authority.release(first["executionId"], credentials(first))
    second = claim(authority, "second")
    assert second["epoch"] == first["epoch"] + 1
    authority.release(first["executionId"], credentials(first))
    assert authority.heartbeat(second["executionId"], {**credentials(second), "ttlSeconds": 60})["state"] == "running"
    with pytest.raises(ValueError):
        authority.submit(first["executionId"], {**credentials(first), "requestId": "late", "result": {"summary": "late"}})


def test_expired_result_and_heartbeat_rejected_assignment_stays_immutable(authority, service):
    record = claim(authority)
    with service.db_for("draft") as db:
        db.execute("UPDATE card_leases SET expires_at=0")
    with pytest.raises(ValueError, match="authoritative"):
        authority.heartbeat(record["executionId"], {**credentials(record), "ttlSeconds": 60})
    assert authority.read_assignment(record["executionId"], **SCOPE, token=record["token"])["assignment"] == record["assignment"]
    with pytest.raises(ValueError):
        authority.submit(record["executionId"], {**credentials(record), "requestId": "late", "result": {"summary": "late"}})


def test_context_change_and_force_release_revoke_authority(authority, service):
    first = claim(authority)
    legacy_save(service)
    with pytest.raises(ValueError, match="specifications"):
        authority.heartbeat(first["executionId"], {**credentials(first), "ttlSeconds": 60})
    CardLeases(service).apply({**SCOPE, "nodeId": "a", "op": "release"}, actor="human")
    with pytest.raises(ValueError, match="authoritative"):
        authority.submit(first["executionId"], {**credentials(first), "requestId": "late", "result": {"summary": "late"}})


def test_active_legacy_claim_conflicts(authority, service):
    CardLeases(service).apply({**SCOPE, "nodeId": "a", "op": "claim", "owner": "old", "ttlSeconds": 60})
    with pytest.raises(ValueError, match="active lease"):
        claim(authority)


def test_simultaneous_claims_have_one_owner(authority, service):
    from backend.canvas.canvas_service import CanvasService
    other = CanvasService(service.root)
    second = ExecutionResults(other)
    barrier = Barrier(2)
    def attempt(args):
        client, request = args
        barrier.wait()
        try:
            return claim(client, request)["executionId"]
        except ValueError:
            return None
    try:
        assert service.db_for("draft") is not other.db_for("draft")
        with ThreadPoolExecutor(2) as pool:
            assert sum(value is not None for value in pool.map(attempt, [(authority, "one"), (second, "two")])) == 1
    finally:
        other.close()


def test_claim_replay_and_failed_transaction_leave_no_partial_enrollment(authority, service, monkeypatch):
    first = claim(authority)
    assert claim(authority)["executionId"] == first["executionId"]
    with pytest.raises(ValueError, match="different content"):
        claim(authority, node="b")
    def fail(*args):
        raise RuntimeError("injected")
    monkeypatch.setattr(Executions, "insert", fail)
    with pytest.raises(RuntimeError):
        claim(authority, "second", "b")
    db = service.db_for("draft")
    assert db.execute("SELECT COUNT(*) FROM opora_execution_epochs WHERE node_id='b'").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM card_leases WHERE node_id='b'").fetchone()[0] == 0


def test_result_rollback_keeps_lease_and_no_receipt(authority, service, monkeypatch):
    record = claim(authority)
    def fail(*args):
        raise RuntimeError("injected")
    monkeypatch.setattr(Executions, "save", fail)
    with pytest.raises(RuntimeError):
        authority.submit(record["executionId"], {**credentials(record), "requestId": "r", "result": {"summary": "ready"}})
    db = service.db_for("draft")
    assert db.execute("SELECT COUNT(*) FROM opora_execution_results").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM card_leases").fetchone()[0] == 1


def test_related_unaccepted_specification_prevents_dispatch(authority, service):
    view = service.view("draft", "draft")
    graph = copy.deepcopy(view["graph"])
    graph["edges"].append({"id": "ab", "source": "a", "target": "b"})
    service.save_graph("draft", "draft", graph, view["digest"])
    legacy_save(service, "b")
    assert not authority.context(**SCOPE, node="a")["available"]


def test_new_accepted_revision_invalidates_existing_run(authority, service):
    from backend.canvas.test_opora_changesets import accept, propose
    record = claim(authority)
    accept(service, propose(service, nodes=("b",)), record["acceptedRevision"])
    with pytest.raises(ValueError, match="changed"):
        authority.heartbeat(record["executionId"], {**credentials(record), "ttlSeconds": 60})


def test_expired_claim_replay_never_creates_new_authority(authority, service):
    record = claim(authority)
    with service.db_for("draft") as db:
        db.execute("UPDATE card_leases SET expires_at=0")
    replay = claim(authority)
    assert replay["executionId"] == record["executionId"] and replay["state"] == "revoked"
    assert replay["epoch"] == record["epoch"]


@pytest.mark.parametrize("result", [{}, {"summary": ""}, {"summary": "x" * 64_001}, {"summary": "ok", "number": float("nan")}])
def test_invalid_result_never_consumes_authority(authority, result):
    record = claim(authority)
    with pytest.raises(ValueError):
        authority.submit(record["executionId"], {**credentials(record), "requestId": "r", "result": result})
    assert authority.heartbeat(record["executionId"], {**credentials(record), "ttlSeconds": 60})["state"] == "running"


@pytest.mark.parametrize("operation", ["heartbeat", "result"])
def test_expiry_during_context_capture_never_renews_or_accepts(authority, service, monkeypatch, operation):
    import backend.canvas.opora_executions as module
    record = claim(authority)
    clock = [record["expiresAt"] - 1]
    original = module.assignment
    def slow_capture(*args):
        captured = original(*args)
        clock[0] = record["expiresAt"] + 1
        return captured
    monkeypatch.setattr(module.time, "time", lambda: clock[0])
    monkeypatch.setattr(module, "assignment", slow_capture)
    with pytest.raises(ValueError, match="authoritative"):
        if operation == "heartbeat":
            authority.heartbeat(record["executionId"], {**credentials(record), "ttlSeconds": 60})
        else:
            authority.submit(record["executionId"], {**credentials(record), "requestId": "late", "result": {"summary": "late"}})
    db = service.db_for("draft")
    assert db.execute("SELECT expires_at FROM card_leases").fetchone()[0] == record["expiresAt"]
    assert db.execute("SELECT COUNT(*) FROM opora_execution_results").fetchone()[0] == 0
