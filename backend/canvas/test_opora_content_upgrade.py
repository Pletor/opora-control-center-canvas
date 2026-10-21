"""Adding content DDL preserves history but cannot renew older sparse coverage."""
import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.test_opora_changesets import SCOPE
from backend.canvas.test_opora_execution_context import claimed
from backend.canvas.test_opora_execution_context import sparse as sparse  # noqa: PLC0414
from backend.canvas.test_opora_graph_initial import empty_graphs as empty_graphs  # noqa: PLC0414
from database.repositories import opora_execution_contexts as private
from database.repositories.opora_context_events import checkpoint, enroll
from database.schema.opora_content_schema import TABLES
from database.schema.project_initialization import initialize_project_schema


def rows(db, table):
    return [tuple(row) for row in db.execute(f"SELECT * FROM {table}")]


def test_content_schema_upgrade_rejects_old_sparse_coverage_without_erasing_history(sparse):
    graphs, _, refs = sparse
    db = graphs.service.db_for("draft")
    # Simulate the preceding release before enrollment, only in the isolated fixture.
    for table in TABLES:
        assert not rows(db, table)
        db.execute(f"DROP TABLE {table}")
    db.commit()
    record = claimed(sparse)
    original_pin = private.read(db, "draft", "draft", record["executionId"])
    preserved_tables = ("opora_context_events", "opora_context_coverage",
                        "opora_execution_context_keys", "opora_execution_context_pins",
                        "opora_spec_revisions", "opora_executions")
    before = {table: rows(db, table) for table in preserved_tables}
    generation = db.execute("PRAGMA schema_version").fetchone()[0]
    assert checkpoint(db, "draft")["sequence"] >= 0
    initialize_project_schema(db)
    db.commit()
    assert db.execute("PRAGMA schema_version").fetchone()[0] > generation
    for table in preserved_tables:
        assert rows(db, table) == before[table]
    with pytest.raises(ValueError, match="schema generation"):
        checkpoint(db, "draft")
    with db:
        db.execute("BEGIN IMMEDIATE")
        with pytest.raises(ValueError, match="schema generation"):
            enroll(db, "draft")
    assert private.read(db, "draft", "draft", record["executionId"]) == original_pin
    reopened = CanvasService(graphs.service.root)
    try:
        reopened_db = reopened.db_for("draft")
        with pytest.raises(ValueError, match="schema generation"):
            checkpoint(reopened_db, "draft")
        assert private.read(reopened_db, "draft", "draft", record["executionId"]) == original_pin
        for table in preserved_tables:
            assert rows(reopened_db, table) == before[table]
        context = ExecutionResults(reopened).context(**SCOPE, node=refs["a"])
        assert context["available"] is True
        assert context.get("contextProtocolVersion", 1) == 1
    finally:
        reopened.close()
