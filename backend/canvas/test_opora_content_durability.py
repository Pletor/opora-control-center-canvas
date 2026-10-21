"""Native content transaction evidence survives failures and process reopening."""
import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.test_opora_content_changes import accepted, change, propose
from backend.canvas.test_opora_execution_context import claimed, prepared
from backend.canvas.test_opora_execution_context import sparse as sparse  # noqa: PLC0414
from backend.canvas.test_opora_executions import credentials
from backend.canvas.test_opora_graph_initial import empty_graphs as empty_graphs  # noqa: PLC0414
from database.repositories.opora_content_records import ContentRecords
from database.repositories.opora_context_events import checkpoint


def test_failed_accept_rolls_back_sql_journal_as_well_as_native_history(sparse, monkeypatch):
    _, authority, refs = sparse
    prepared(sparse)
    db = authority.canvas.db_for("draft")
    before = checkpoint(db, "draft")
    item = propose(sparse, [change("text", refs["a"], "text", "Must roll back")])
    original = ContentRecords.insert

    def fail(self, record, *, manifest=False):
        if manifest:
            raise ValueError("Injected manifest failure")
        return original(self, record, manifest=manifest)

    monkeypatch.setattr(ContentRecords, "insert", fail)
    with pytest.raises(ValueError, match="manifest failure"):
        accepted(sparse, item)
    assert checkpoint(db, "draft") == before
    assert authority.canvas.texts.read(("draft", "draft", refs["a"]))["revision"] == 0


def test_reopen_retains_accepted_content_and_sparse_execution_origin(sparse):
    _, authority, refs = sparse
    manifest_revision = accepted(sparse, propose(sparse, [change("text", refs["a"], "text", "Persisted")]))
    record = claimed(sparse)
    root = authority.canvas.root
    authority.canvas.close()
    canvas = CanvasService(root)
    try:
        current = ExecutionResults(canvas)
        manifest = ContentRecords(canvas.db_for("draft"), "draft", "draft").read(manifest_revision["contentManifestId"], manifest=True)
        assert any(item["value"] == "Persisted" for item in manifest["entries"])
        renewed = current.heartbeat(record["executionId"], {**credentials(record), "ttlSeconds": 60})
        assert renewed["assignmentDigest"] == record["assignmentDigest"]
        assert renewed["assignment"] == record["assignment"]
    finally:
        canvas.close()
