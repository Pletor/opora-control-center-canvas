"""Actual completed executions survive graph deletion and transactional rollback."""
import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.graph import encode
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.opora_graph_change_acceptance import OporaGraphChangeAcceptance
from backend.canvas.opora_graph_changes import OporaGraphChanges
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.test_opora_changesets import AGENT, HUMAN, SCOPE
from backend.canvas.test_opora_graph_proposals import accept, proposal
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State, default_done, default_state
from backend.editor.node.test_removals import state_node
from database.repositories.opora_changesets import ChangesetRepository


@pytest.fixture
def completed(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    try:
        graphs = OporaGraphProposals(canvas)
        initial = proposal(graphs, plan={"nodes": [
            {"ref": "remove", "kind": "node", "name": "Completed execution", "spec": {
                "goal": "Do the work", "non_goals": "Other work", "acceptance": "Report results"}},
            {"ref": "keep", "kind": "node", "name": "Surviving task"}]})
        baseline = accept(graphs, initial)
        remove = initial["refs"]["remove"]
        db = canvas.db_for("draft")
        state = default_state()
        state["nodes"] = {remove: state_node()}
        db.execute("INSERT INTO desktop_v3_state VALUES('draft','draft',1,?,'initial')", (encode(state),))
        db.execute("INSERT INTO agent_workspace_revisions VALUES('draft','draft',?,1,'{}','human','initial')", (remove,))
        db.execute("INSERT INTO node_text_revisions VALUES('draft','draft',?,1,'Historical note','initial')", (remove,))
        db.commit()
        executions = ExecutionResults(canvas)
        context = executions.context(**SCOPE, node=remove)
        record = executions.claim({**SCOPE, "nodeId": remove, "requestId": "execution", "ttlSeconds": 900,
                                   "expectedAcceptedHead": baseline["id"], "expectedContextVersion": context["contextVersion"]}, "agent:worker")
        payload = {**SCOPE, "token": record["token"], "epoch": record["epoch"], "requestId": "result",
                   "result": {"summary": "Completed work before removal"}}
        receipt = executions.submit(record["executionId"], payload)
        yield canvas, initial, baseline, record, payload, receipt
    finally:
        canvas.close()


def deletion(canvas, remove):
    changes = OporaGraphChanges(canvas)
    context = changes.specifications.context("draft", "draft")
    item = changes.create({**SCOPE, "parentRevision": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
                           "subject": "Archive completed card", "plan": {"removeNodes": [remove]}}, AGENT)
    payload = {**SCOPE, "expectedAcceptedHead": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
               "adoptBaseGraphDigest": None, "reviewedChangesId": item["id"]}
    return item, payload


HISTORY = ("node_spec_revisions", "node_text_revisions", "agent_workspace_revisions", "opora_executions",
           "opora_execution_epochs", "opora_execution_results", "graph_recoveries", "removal_restores")


def history(db):
    return {table: [tuple(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY rowid")] for table in HISTORY}


def test_deleted_accepted_card_keeps_all_history_receipt_replay_and_future_plans(completed):
    canvas, initial, baseline, execution, result_payload, receipt = completed
    removed = initial["refs"]["remove"]
    item, payload = deletion(canvas, removed)
    db = canvas.db_for("draft")
    before = history(db)
    accepted = OporaGraphChangeAcceptance(canvas).accept(item["id"], payload, HUMAN)
    assert history(db) == before
    assert removed not in {node["id"] for node in canvas.view("draft", "draft")["graph"]["nodes"]}
    assert removed not in {doc["nodeId"] for doc in accepted["documents"]}
    assert removed in {doc["nodeId"] for doc in ChangesetRepository(db, "draft", "draft").read(baseline["id"])["documents"]}
    assert removed not in DesktopV3State(canvas).current("draft", "draft")["state"]["nodes"]
    assert item["stateEffects"]["effects"]["removedNodes"][removed] == state_node()
    assert ExecutionResults(canvas).submit(execution["executionId"], result_payload) == receipt
    graphs = OporaGraphProposals(canvas)
    next_item = proposal(graphs, "Further plan")
    later = accept(graphs, next_item)
    assert later["parentRevision"] == accepted["id"]
    assert OporaGraphChangeAcceptance(canvas).accept(item["id"], payload, HUMAN)["id"] == accepted["id"]
    assert ChangesetRepository(db, "draft", "draft").head() == later["id"]


def test_failure_after_graph_state_manifest_and_revision_rolls_back_everything(completed, monkeypatch):
    canvas, initial, _baseline, _execution, _payload, _receipt = completed
    item, payload = deletion(canvas, initial["refs"]["remove"])
    db = canvas.db_for("draft")
    before = list(db.iterdump())
    graph = canvas.view("draft", "draft")["graph"]
    state = DesktopV3State(canvas).current("draft", "draft")

    def fail(*args):
        raise RuntimeError("failure before accepted head advance")

    monkeypatch.setattr(ChangesetRepository, "advance", fail)
    with pytest.raises(RuntimeError, match="before accepted head"):
        OporaGraphChangeAcceptance(canvas).accept(item["id"], payload, HUMAN)
    assert list(db.iterdump()) == before
    assert canvas.view("draft", "draft")["graph"] == graph
    assert DesktopV3State(canvas).current("draft", "draft") == state


def test_parent_closed_after_proposal_blocks_acceptance_and_rebase(completed):
    canvas, initial, _baseline, _execution, _payload, _receipt = completed
    parent = initial["refs"]["keep"]
    changes = OporaGraphChanges(canvas)
    context = changes.specifications.context("draft", "draft")
    item = changes.create({**SCOPE, "parentRevision": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"],
                           "subject": "Extend parent", "plan": {"updateNodes": [{"id": parent, "fields": {"purpose": "Extended"}}],
                           "nodes": [{"ref": "child", "kind": "node", "name": "Child", "parent": "@" + parent}]}}, AGENT)
    db = canvas.db_for("draft")
    stored = DesktopV3State(canvas).current("draft", "draft")
    state = {**stored["state"], "nodes": {**stored["state"]["nodes"], parent: state_node(done={
        **default_done(), "confirmed": True, "at": "2026-10-21T00:00:00Z"})}}
    db.execute("UPDATE desktop_v3_state SET revision=revision+1,state=?,saved_at='closed-parent'", (encode(state),))
    db.commit()
    payload = {**SCOPE, "expectedAcceptedHead": context["acceptedHead"], "expectedGraphDigest": context["graphDigest"]}
    with pytest.raises(ValueError, match="reopen confirmed"):
        OporaGraphChangeAcceptance(canvas).accept(item["id"], {**payload, "adoptBaseGraphDigest": None,
                                                             "reviewedChangesId": item["id"]}, HUMAN)
    with pytest.raises(ValueError, match="reopen confirmed"):
        changes.rebase(item["id"], payload, AGENT)
