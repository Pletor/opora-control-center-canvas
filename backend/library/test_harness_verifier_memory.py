"""Optional memory bridge preserves native report transactions and replay admission."""
import sys
from types import SimpleNamespace

import pytest

from backend.library.test_harness_verifier import authority as authority  # noqa: PLC0414
from backend.library.test_harness_verifier import payload
from backend.library.test_harness_verifier import service as service  # noqa: PLC0414
from backend.library.test_harness_verifier import setup as setup  # noqa: PLC0414

MODULE = "database.repositories.harness_fixture_memory"


def test_missing_memory_integration_is_explicit_without_losing_native_evidence(setup, monkeypatch):
    monkeypatch.setitem(sys.modules, MODULE, None)
    verifier, _, _, record, calls, _ = setup
    result = verifier.verify(payload(record))
    assert result["memoryDelivery"] == {"available": False}
    assert result["report"]["independentlyVerified"] is True
    assert verifier.verify(payload(record)) == result
    assert len(calls) == 1


def test_memory_enqueue_sees_source_within_same_write_transaction(setup, monkeypatch):
    verifier, _, _, record, calls, _ = setup
    queued = []
    def enqueue(db, project, workspace, identifier):
        assert db.in_transaction
        source = db.execute("SELECT digest FROM opora_verification_reports WHERE verification_id=? "
                            "AND project_id=? AND workspace_id=?", (identifier, project, workspace)).fetchone()
        assert source is not None
        queued.append((identifier, source[0]))
    monkeypatch.setitem(sys.modules, MODULE, SimpleNamespace(enqueue=enqueue))
    result = verifier.verify(payload(record))
    assert result["memoryDelivery"] == {"available": True}
    assert queued == [(result["id"], result["report"]["reportDigest"])]
    assert verifier.verify(payload(record)) == result
    assert queued == [queued[0], queued[0]]  # Source helper owns idempotence; no container rerun.
    assert len(calls) == 1


def test_projection_failure_rolls_back_report_and_keeps_consumed_admission(setup, monkeypatch):
    verifier, canvas, _, record, calls, _ = setup
    def fail(*args):
        raise RuntimeError("memory projection unavailable")
    monkeypatch.setitem(sys.modules, MODULE, SimpleNamespace(enqueue=fail))
    with pytest.raises(RuntimeError, match="memory projection unavailable"):
        verifier.verify(payload(record))
    db = canvas.db_for("draft")
    assert db.execute("SELECT COUNT(*) FROM opora_verification_requests").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM opora_verification_reports").fetchone()[0] == 0
    assert verifier.verify(payload(record))["report"] is None
    assert len(calls) == 1
