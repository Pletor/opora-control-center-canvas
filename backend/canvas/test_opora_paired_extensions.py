"""Rejected pair claims cannot mutate native receipts or authority; authentication runs first."""
import pytest

from backend.canvas.test_opora_execution_context import claimed, credentials
from backend.canvas.test_opora_execution_context import sparse as sparse  # noqa: PLC0414
from backend.canvas.test_opora_graph_initial import empty_graphs as empty_graphs  # noqa: PLC0414
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State


def test_invalid_paired_report_rolls_back_and_preserves_execution(sparse):
    _, authority, _ = sparse
    record = claimed(sparse)
    db = authority.canvas.db_for("draft")
    before = tuple(db.execute("SELECT token,expires_at FROM card_leases").fetchone())
    with pytest.raises(ValueError, match="Invalid Harness paired evaluation"):
        authority.submit(record["executionId"], {**credentials(record), "requestId": "invalid-pair",
                         "result": {"summary": "invalid pair", "harnessPairedEvaluation": {"promotionAllowed": True}}})
    assert db.execute("SELECT COUNT(*) FROM opora_execution_results").fetchone()[0] == 0
    assert tuple(db.execute("SELECT token,expires_at FROM card_leases").fetchone()) == before
    assert authority.heartbeat(record["executionId"], {**credentials(record), "ttlSeconds": 60})["state"] == "running"


def test_pair_claim_does_not_bypass_authentication(sparse):
    _, authority, _ = sparse
    record = claimed(sparse)
    with pytest.raises(ValueError, match="credential or epoch"):
        authority.submit(record["executionId"], {**credentials(record), "token": "0" * 64,
                         "requestId": "foreign-pair", "result": {"summary": "foreign pair", "harnessPairedEvaluation": {}}})
    assert authority.canvas.db_for("draft").execute("SELECT COUNT(*) FROM opora_execution_results").fetchone()[0] == 0


def test_rejected_pair_does_not_store_decisions_and_valid_retry_keeps_new_main_behavior(sparse):
    _, authority, _ = sparse
    record = claimed(sparse)
    state = DesktopV3State(authority.canvas)
    before = state.read(project="draft", workspace="draft")
    payload = {**credentials(record), "requestId": "decision-pair",
               "result": {"summary": "work", "decisions": ["Keep pinned script versions"],
                          "harnessPairedEvaluation": {"promotionAllowed": True}}}
    with pytest.raises(ValueError, match="Invalid Harness paired evaluation"):
        authority.submit(record["executionId"], payload)
    assert state.read(project="draft", workspace="draft") == before
    payload["result"].pop("harnessPairedEvaluation")
    receipt = authority.submit(record["executionId"], payload)
    assert authority.submit(record["executionId"], payload) == receipt
    decisions = state.read(project="draft", workspace="draft")["state"]["decisions"]
    assert len(decisions) == len(before["state"]["decisions"]) + 1
    assert decisions[-1]["executionId"] == record["executionId"]
    assert receipt["decisionIds"] == [decisions[-1]["id"]]
