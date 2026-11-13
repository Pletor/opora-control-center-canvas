"""Pojistka budget: enforce drží vyčerpanou kartu, warn pustí další pokus, zapíše ho a evidence rozpočtu zůstane čitelná."""
import pytest

from backend.app import error_log, errors, guards
from backend.canvas.opora_execution_budgets import ExecutionBudgets
from backend.canvas.test_opora_changesets import SCOPE
from backend.canvas.test_opora_execution_budgets import configure, v2
from backend.canvas.test_opora_executions import authority as authority  # noqa: PLC0414
from backend.canvas.test_opora_executions import credentials
from backend.canvas.test_opora_executions import service as service  # noqa: PLC0414


@pytest.fixture
def exhausted(authority):
    errors.configure(authority.canvas.root)
    guards.configure(authority.canvas.root)
    configure(authority, limits={"maxRunSeconds": 60, "maxAttempts": 1, "maxRepairRounds": 0})
    first = v2(authority)
    authority.release(first["executionId"], credentials(first))
    yield authority
    error_log.drain()
    guards.configure(None)
    errors.configure(None)


def test_enforce_blocks_and_warn_admits_next_attempt(exhausted):
    assert "exhausted" in exhausted.context(**SCOPE, node="a")["unavailableReason"]
    with pytest.raises(ValueError, match="exhausted"):
        v2(exhausted, "second")
    guards.set_mode("budget", "draft", "warn", ("human", None), "karta dostane ještě jeden pokus")
    second = v2(exhausted, "second")
    assert second["budget"]["attempt"] == 2
    exhausted.release(second["executionId"], credentials(second))
    status = ExecutionBudgets(exhausted.canvas).context(**SCOPE, nodeId="a", actor="human")
    assert status["attemptsUsed"] == 2 and status["blockedReason"] is None
    error_log.drain()
    assert any(r["message"].startswith("pojistka budget ve warn") for r in errors.read() if r["kind"] == "blocked")
