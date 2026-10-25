"""Server policy caps cumulative admissions using the existing persistent request ledger."""
import json
import os

import pytest

from backend.canvas.test_opora_executions import claim, credentials
from backend.library import harness_verifier as module
from backend.library.harness_verifier import HarnessVerifier
from backend.library.test_harness_verifier import authority as authority  # noqa: PLC0414
from backend.library.test_harness_verifier import payload
from backend.library.test_harness_verifier import service as service  # noqa: PLC0414
from backend.library.test_harness_verifier import setup as setup  # noqa: PLC0414
from database.repositories.opora_verifications import Verifications


def limit(monkeypatch, value):
    config = json.loads(os.environ["OPORA_HARNESS_VERIFIER"])
    config["maxExperiments"] = value
    monkeypatch.setenv("OPORA_HARNESS_VERIFIER", json.dumps(config))


def test_zero_ceiling_never_admits_or_launches(setup, monkeypatch):
    verifier, canvas, _, record, calls, _ = setup
    limit(monkeypatch, 0)
    with pytest.raises(ValueError, match="ceiling exhausted"):
        verifier.verify(payload(record))
    assert calls == []
    assert canvas.db_for("draft").execute("SELECT COUNT(*) FROM opora_verification_requests").fetchone()[0] == 0


def test_restart_epoch_and_replay_do_not_refund_spent_capacity(setup, monkeypatch):
    verifier, canvas, authority, record, calls, _ = setup
    limit(monkeypatch, 1)
    original = verifier.verify(payload(record))
    restarted = HarnessVerifier(canvas)
    limit(monkeypatch, 0)
    assert restarted.verify(payload(record)) == original
    assert len(calls) == 1
    authority.release(record["executionId"], credentials(record))
    successor = claim(authority, request="new-epoch")
    limit(monkeypatch, 1)
    with pytest.raises(ValueError, match="ceiling exhausted"):
        restarted.verify(payload(successor))
    assert len(calls) == 1
    # Only a server policy change can grant more cumulative capacity.
    limit(monkeypatch, 2)
    assert restarted.verify(payload(successor))["report"]["outcome"] == "passed"
    assert len(calls) == 2


def test_deleted_report_recovery_stays_consumed_without_another_launch(setup, monkeypatch):
    verifier, canvas, authority, record, calls, _ = setup
    limit(monkeypatch, 1)
    first = verifier.verify(payload(record))
    db = canvas.db_for("draft")
    with db:
        db.execute("DELETE FROM opora_verification_reports WHERE verification_id=?", (first["id"],))
        request = json.loads(db.execute("SELECT record FROM opora_verification_requests WHERE id=?", (first["id"],)).fetchone()[0])
        request["deadlineAt"] = 0
        db.execute("UPDATE opora_verification_requests SET record=? WHERE id=?", (json.dumps(request), first["id"]))
    limit(monkeypatch, 0)
    assert HarnessVerifier(canvas).verify(payload(record))["report"]["outcome"] == "inconclusive"
    assert len(calls) == 1
    limit(monkeypatch, 1)
    other = claim(authority, request="other-card", node="b")
    with pytest.raises(ValueError, match="ceiling exhausted"):
        verifier.verify(payload(other))


def test_inconclusive_attempt_consumes_capacity(setup, monkeypatch):
    verifier, canvas, authority, record, _, _ = setup
    limit(monkeypatch, 1)
    monkeypatch.setattr(module, "run_paired_fixture", lambda *args: (_ for _ in ()).throw(OSError("unavailable")))
    assert verifier.verify(payload(record))["report"]["outcome"] == "inconclusive"
    other = claim(authority, request="other-card", node="b")
    with pytest.raises(ValueError, match="ceiling exhausted"):
        HarnessVerifier(canvas).verify(payload(other))
    assert canvas.db_for("draft").execute("SELECT COUNT(*) FROM opora_verification_requests").fetchone()[0] == 1


def test_other_workspace_and_formal_requests_do_not_consume_scope_budget(setup, monkeypatch):
    verifier, canvas, authority, record, calls, _ = setup
    limit(monkeypatch, 2)
    first = verifier.verify(payload(record))
    with canvas.db_for("draft") as db:
        Verifications(db, "draft", "foreign").insert({**first, "id": "foreign", "workspace": "foreign", "requestId": "foreign"})
        Verifications(db, "draft", "draft").insert({**first, "id": "formal", "requestId": "formal", "domain": "formal", "origin": {"kind": "formal"}})
    other = claim(authority, request="other-card", node="b")
    assert verifier.verify(payload(other))["report"]["outcome"] == "passed"
    assert len(calls) == 2
