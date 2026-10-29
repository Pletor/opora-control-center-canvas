"""Archive, cancellation and destructive restore retain immutable formal evidence."""
import sqlite3

import pytest

from backend.canvas.opora_execution_budget_cancel import cancel
from backend.canvas.opora_execution_budgets import ExecutionBudgets
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.opora_verifications import OporaVerifications
from backend.canvas.test_opora_reconciliation import (
    reconciliation_project as reconciliation_project,  # noqa: PLC0414
)
from backend.canvas.test_opora_review_fixtures import HUMAN
from backend.canvas.test_opora_review_fixtures import (
    evidence_project as evidence_project,  # noqa: PLC0414
)
from backend.canvas.test_opora_verifications import artifact, verification
from backend.canvas.workspace_graph_storage import refuse_authority_restore
from backend.project.worktrees.workspace_archive import WorkspaceArchive
from database.schema.opora_verification_schema import TABLES
from database.schema.project_initialization import initialize_project_schema
from database.schema.project_schema import PROJECT_TABLES


def test_real_archive_and_v2_human_cancellation(reconciliation_project):
    service, scope, pin = reconciliation_project
    policy = ExecutionBudgets(service).configure({**scope, "nodeId": "card", "expectedPolicyHead": None,
        "expectedAcceptedHead": pin["expectedAcceptedHead"], "requestId": "budget",
        "limits": {"maxRunSeconds": 60, "maxAttempts": 2, "maxRepairRounds": 0}}, HUMAN)
    authority = ExecutionResults(service)
    context = authority.context(**scope, node="card")
    execution = authority.claim({**scope, "nodeId": "card", "expectedAcceptedHead": context["acceptedHead"],
        "expectedContextVersion": context["contextVersion"], "expectedBudgetPolicyHead": policy["policyHead"],
        "previousExecutionId": None, "requestId": "claim", "ttlSeconds": 60}, "agent:formal")
    ledger = OporaVerifications(service)
    credentials = {**scope, "token": execution["token"], "epoch": execution["epoch"]}
    request = {**credentials, "executionId": execution["executionId"], "requestId": "formal", "verification": verification()}
    saved = ledger.create(request)
    cancel(service, execution["executionId"], {**scope, "epoch": execution["epoch"], "requestId": "cancel"}, HUMAN)
    with pytest.raises(ValueError):
        ledger.submit_report(saved["id"], {**credentials, "requestId": "late", "report": {
            "outcome": "passed", "checkedClaims": ["identity"], "summary": "Late report",
            "artifacts": [artifact("stdout", "stdout")]}})
    assert ledger.create(request)["id"] == saved["id"]
    archived = WorkspaceArchive(service).archive(scope["workspace"],
        {"project": scope["project"], "reason": "Formal archive proof", "confirmed": True})
    assert archived["archived"] == scope["workspace"]
    detail = ledger.read(saved["id"], **scope)
    assert detail["verification"]["artifacts"][0]["available"]
    fingerprint = detail["verification"]["artifacts"][0]["sha256"]
    assert ledger.artifact(saved["id"], fingerprint, **scope).startswith(b"theorem")
    assert ledger.history(**scope)["requests"][0]["id"] == saved["id"]


@pytest.mark.parametrize("table", TABLES)
def test_each_populated_table_blocks_restore_even_orphaned(table):
    db = sqlite3.connect(":memory:")
    try:
        initialize_project_schema(db)
        columns = list(db.execute(f"PRAGMA table_info({table})"))
        values = [0 if column[2] == "INTEGER" else b"x" if column[2] == "BLOB" else "x" for column in columns]
        db.execute(f"INSERT INTO {table} VALUES({','.join('?' for _ in columns)})", values)
        assert PROJECT_TABLES[table] == "project_id"
        with pytest.raises(ValueError, match="formal verification history"):
            refuse_authority_restore(db)
    finally:
        db.close()
