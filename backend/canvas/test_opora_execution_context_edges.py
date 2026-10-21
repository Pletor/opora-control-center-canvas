"""Sparse origin survives restart and unrelated changes; authority fails closed."""
import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.opora_execution_context import prepare
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.test_opora_execution_context import claimed, prepared
from backend.canvas.test_opora_execution_context import sparse as sparse  # noqa: PLC0414
from backend.canvas.test_opora_execution_lineage import graph_change
from backend.canvas.test_opora_executions import credentials
from backend.canvas.test_opora_graph_initial import empty_graphs as empty_graphs  # noqa: PLC0414
from database.repositories import opora_execution_contexts as private


def test_reopen_preserves_private_key_pin_binding_and_origin(sparse):
    _, authority, _ = sparse
    record = claimed(sparse)
    canvas = authority.canvas
    original_pin = private.read(canvas.db_for("draft"), "draft", "draft", record["executionId"])
    original_key = private.key(canvas.db_for("draft"), "draft")
    root = canvas.root
    canvas.close()
    reopened = CanvasService(root)
    try:
        current = ExecutionResults(reopened)
        assert private.key(reopened.db_for("draft"), "draft") == original_key
        assert private.read(reopened.db_for("draft"), "draft", "draft", record["executionId"]) == original_pin
        renewed = current.heartbeat(record["executionId"], {**credentials(record), "ttlSeconds": 60})
        assert renewed["assignmentDigest"] == record["assignmentDigest"]
        assert renewed["assignment"] == record["assignment"]
        assert renewed["contextValidation"]["checkedAcceptedRevision"] == record["acceptedRevision"]
        receipt = current.submit(record["executionId"], {**credentials(record), "requestId": "reopened", "result": {"summary": "Done"}})
        assert receipt["contextValidation"]["originAcceptedRevision"] == record["acceptedRevision"]
    finally:
        reopened.close()


def test_unrelated_accepted_graph_change_and_sql_writer_rollback(sparse):
    graphs, authority, refs = sparse
    record = claimed(sparse)
    accepted = graph_change(graphs, {"updateNodes": [{"id": refs["b"], "fields": {"name": "Renamed B"}}]})
    db = authority.canvas.db_for("draft")
    db.execute("BEGIN IMMEDIATE")
    db.execute("INSERT INTO node_text_revisions VALUES(?,?,?,?,?,?)", ("draft", "draft", refs["a"], 1, "Rolled back", "now"))
    db.rollback()
    renewed = authority.heartbeat(record["executionId"], {**credentials(record), "ttlSeconds": 60})
    assert renewed["contextValidation"]["checkedAcceptedRevision"] == accepted["id"]
    assert renewed["assignmentDigest"] == record["assignmentDigest"]


def test_new_result_rejected_after_slow_validation_expires_lease(sparse, monkeypatch):
    _, authority, _ = sparse
    record = claimed(sparse)
    from backend.canvas import opora_execution_context_validation as validation
    original = validation.replay

    def expired(db, *args, **kwargs):
        result = original(db, *args, **kwargs)
        db.execute("UPDATE card_leases SET expires_at=0")
        return result

    monkeypatch.setattr(validation, "replay", expired)
    with pytest.raises(ValueError, match="authoritative"):
        authority.submit(record["executionId"], {**credentials(record), "requestId": "late", "result": {"summary": "Late"}})
    assert authority.receipts(record["executionId"], "draft", "draft")["results"] == []


def test_unknown_persisted_version_rejected_and_failed_pin_write_rolls_back(sparse, monkeypatch):
    _, authority, _ = sparse
    context = prepared(sparse)
    original = private.insert

    def failed(*args):
        raise ValueError("Injected private pin failure.")

    monkeypatch.setattr(private, "insert", failed)
    with pytest.raises(ValueError, match="pin failure"):
        claimed(sparse, context=context)
    db = authority.canvas.db_for("draft")
    assert db.execute("SELECT COUNT(*) FROM card_leases").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM opora_execution_epochs").fetchone()[0] == 0
    monkeypatch.setattr(private, "insert", original)
    record = claimed(sparse, context=context)
    with authority.transaction("draft", "draft") as repo:
        stored = repo.read(record["executionId"])
        stored["contextProtocolVersion"] = 3
        repo.save(stored)
    with pytest.raises(ValueError, match="persisted"):
        authority.heartbeat(record["executionId"], {**credentials(record), "ttlSeconds": 60})


def test_explicit_prepare_rejects_legacy_spec_only_manifest(sparse):
    _, authority, refs = sparse
    from backend.canvas.opora_changesets import OporaChangesets
    project = authority.canvas.project_hub.empty_project({"name": "Legacy plan", "confirmed": True})
    pid = project["id"]
    view = authority.canvas.view(pid, "draft")
    from backend.canvas.test_graph_card import node
    authority.canvas.save_graph(pid, "draft", {"nodes": [node("legacy")], "edges": []}, view["digest"])
    changesets = OporaChangesets(authority.canvas)
    context = changesets.context(pid, "draft")
    changesets.baseline({"project": pid, "workspace": "draft", "subject": "Legacy specs", "expectedAcceptedHead": None,
                        "expectedGraphDigest": context["graphDigest"], "expectedSpecificationsVersion": context["specificationsVersion"]},
                       {"kind": "human", "name": "Reviewer"})
    with pytest.raises(ValueError):
        prepare(authority, {"project": pid, "workspace": "draft", "nodeId": refs["a"], "contextProtocolVersion": 2})


def test_actual_empty_project_archive_revokes_sparse_execution(sparse):
    _, authority, _ = sparse
    from backend.canvas.opora_graph_acceptance import OporaGraphAcceptance
    from backend.canvas.opora_graph_proposals import OporaGraphProposals
    from backend.editor.node.removals import RemovalService

    canvas = authority.canvas
    project = canvas.project_hub.empty_project({"name": "Archive proof", "confirmed": True})
    scope = {"project": project["id"], "workspace": "draft"}
    graphs = OporaGraphProposals(canvas)
    context = graphs.context(**scope)
    item = graphs.create({**scope, "parentRevision": None, "expectedGraphDigest": context["graphDigest"],
                          "subject": "Initial plan", "plan": {"nodes": [{"ref": "a", "name": "Task", "kind": "node"}]}},
                         {"kind": "agent", "name": "Builder"})
    OporaGraphAcceptance(canvas).accept(item["id"], {**scope, "expectedAcceptedHead": None,
        "expectedGraphDigest": context["graphDigest"], "adoptBaseGraphDigest": item["graphDigest"] if item["requiresBaseAdoption"] else None},
        {"kind": "human", "name": "Reviewer"})
    context = prepare(authority, {**scope, "nodeId": item["refs"]["a"], "contextProtocolVersion": 2})
    record = authority.claim({**scope, "nodeId": item["refs"]["a"], "contextProtocolVersion": 2,
        "requestId": "archive", "ttlSeconds": 60, "expectedAcceptedHead": context["acceptedHead"],
        "expectedContextVersion": context["contextVersion"]}, "agent:worker")
    removal = RemovalService(canvas)
    _, preview = removal.project_plan(project["id"], "main", project["id"])
    assert removal.remove_project({"project": project["id"], "workspace": "main", "target": project["id"],
                                   "kind": "project", "digest": preview["digest"], "confirmed": True})["removedProject"] == project["id"]
    with pytest.raises(ValueError):
        authority.heartbeat(record["executionId"], {**scope, "token": record["token"], "epoch": record["epoch"], "ttlSeconds": 60})
