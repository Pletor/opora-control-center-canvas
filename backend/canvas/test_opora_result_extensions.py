import pytest

from backend.canvas.test_opora_execution_context import claimed, credentials, sparse
from backend.canvas.test_opora_graph_initial import empty_graphs


def test_invalid_harness_metadata_rolls_back_receipt_and_preserves_lease(sparse):
    _, authority, _ = sparse
    record = claimed(sparse)
    db = authority.canvas.db_for("draft")
    before = tuple(db.execute("SELECT token,expires_at FROM card_leases").fetchone())
    with pytest.raises(ValueError, match="Invalid Harness invocation metadata"):
        authority.submit(record["executionId"], {**credentials(record), "requestId": "invalid-extension",
                            "result": {"summary": "work", "harnessInvocations": [{}]}})
    assert db.execute("SELECT COUNT(*) FROM opora_execution_results").fetchone()[0] == 0
    assert tuple(db.execute("SELECT token,expires_at FROM card_leases").fetchone()) == before
    assert authority.heartbeat(record["executionId"], {**credentials(record), "ttlSeconds": 60})["state"] == "running"


def test_authentication_precedes_extension_validation(sparse):
    _, authority, _ = sparse
    record = claimed(sparse)
    payload = {**credentials(record), "token": "0" * 64, "requestId": "unauthenticated",
               "result": {"summary": "work", "harnessInvocations": [{}]}}
    with pytest.raises(ValueError, match="credential or epoch"):
        authority.submit(record["executionId"], payload)
    db = authority.canvas.db_for("draft")
    assert db.execute("SELECT COUNT(*) FROM opora_execution_results").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM card_leases").fetchone()[0] == 1


def test_legacy_result_with_stdout_still_submits_without_extension(sparse):
    _, authority, _ = sparse
    record = claimed(sparse)
    receipt = authority.submit(record["executionId"], {**credentials(record), "requestId": "legacy-result",
                           "result": {"summary": "legacy success", "stdout": "existing output", "args": ["build"]}})
    assert receipt["state"] == "reported"
    assert receipt["result"]["stdout"] == "existing output"
