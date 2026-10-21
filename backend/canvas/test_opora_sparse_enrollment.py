"""Sparse context v2 enrollment: dry-run backfill writes nothing, real backfill is idempotent, new cards enroll."""
from backend.canvas import opora_sparse_enrollment as sparse_enrollment
from backend.canvas.opora_auto_rebase_manager import AutoRebaseManager
from backend.canvas.opora_sparse_backfill import main
from backend.canvas.test_opora_execution_context import sparse
from backend.canvas.test_opora_graph_initial import empty_graphs
from backend.canvas.test_opora_graph_proposals import accept, proposal

__all__ = ["empty_graphs", "sparse"]


def rows(canvas):
    return [tuple(row) for row in canvas.db_for("draft").execute(
        "SELECT node_id,status,source FROM opora_sparse_enrollment ORDER BY node_id").fetchall()]


def test_backfill_dry_run_then_idempotent_enrollment(sparse):
    _, authority, refs = sparse
    canvas = authority.canvas
    dry = sparse_enrollment.backfill(canvas, "draft", dry_run=True)
    assert dry["dryRun"] and sorted(item["nodeId"] for item in dry["items"]) == sorted(refs.values())
    assert {item["status"] for item in dry["items"]} == {"would_enroll"} and rows(canvas) == []
    real = sparse_enrollment.backfill(canvas, "draft")
    assert {item["status"] for item in real["items"]} == {"enrolled"}
    assert {row[2] for row in rows(canvas)} == {"backfill"}
    assert sparse_enrollment.backfill(canvas, "draft")["items"] == []
    status = sparse_enrollment.status(canvas, "draft", "draft")
    assert {item["defaultContextProtocolVersion"] for item in status["items"]} == {2}


def test_new_cards_enroll_automatically_but_existing_wait_for_backfill(sparse):
    graphs, authority, refs = sparse
    canvas = authority.canvas
    manager = AutoRebaseManager(canvas)
    manager.run_once()
    assert rows(canvas) == []
    item = proposal(graphs, plan={"nodes": [{"ref": "c", "kind": "node", "name": "C"}]})
    accept(graphs, item)
    manager.run_once()
    assert rows(canvas) == [(item["refs"]["c"], "enrolled", "auto")]
    status = {entry["nodeId"]: entry["defaultContextProtocolVersion"]
              for entry in sparse_enrollment.status(canvas, "draft", "draft")["items"]}
    assert status[refs["a"]] == 1 and status[item["refs"]["c"]] == 2


def test_cli_dry_run_prints_plan_without_writes(sparse, capsys):
    _, authority, _ = sparse
    root = authority.canvas.root
    assert main(["--data", str(root), "--project", "draft", "--dry-run"]) == 0
    assert '"dryRun": true' in capsys.readouterr().out
    assert rows(authority.canvas) == []
