"""Native full text, human authority, CAS and uncertain receipt behavior."""
import pytest

from backend.api.brain_opora.test_canvas_capability_routes import setup as capability_setup
from backend.canvas.activity_log import HumanRequired
from backend.canvas.payload_errors import NextStep
from backend.canvas.test_graph_card import node
from backend.editor.brief_vault import operation_reviews as ops
from backend.editor.brief_vault.brief_vault import BriefVault

setup = capability_setup
SESSION = {"worker_name": "heart", "role": "heart", "id": "test-heart", "workspace_id": "draft"}


def seed(service):
    view = service.view("draft", "draft")
    service.save_graph("draft", "draft", {"nodes": [node("a")], "edges": []}, view["digest"])


def invoke(service, operation, key, **kwargs):
    return ops.invoke(service, "draft", "draft", SESSION, operation, key, **kwargs)


def test_fragment_receipt_replay_exact_text_and_human_delete_restore(setup):
    _, service, _ = setup
    seed(service)
    command = {"op": "create", "title": "Original", "text": "Exact full source", "discipline": "be", "scopeNodeId": ""}
    created = invoke(service, command, "create")
    assert created["verified"] and created["state"] == "persisted"
    fragment = created["result"]["fragment"]
    assert invoke(service, command, "create") == created
    with pytest.raises(NextStep):
        invoke(service, {**command, "text": "Changed"}, "create")
    deletion = {"op": "delete", "fragmentId": fragment["id"], "expectedRevision": 1, "note": "Explicit removal"}
    pending = invoke(service, deletion, "delete")
    assert pending["state"] == "awaiting_human"
    assert not BriefVault(service).fragment("draft", "draft", fragment["id"])["fragment"]["deleted"]
    intent = pending["result"]
    with pytest.raises(HumanRequired):
        ops.decide(service, "draft", "draft", "delete", intent["digest"], "accept", "agent")
    result = ops.decide(service, "draft", "draft", "delete", intent["digest"], "accept", "human")
    assert result["result"]["fragment"]["deleted"]
    assert ops.decide(service, "draft", "draft", "delete", intent["digest"], "accept", "human") == result
    restore = invoke(service, {"op": "restore", "fragmentId": fragment["id"], "expectedRevision": 2, "revision": 1, "note": "Restore reviewed source"}, "restore")
    ops.decide(service, "draft", "draft", "restore", restore["result"]["digest"], "accept", "human")
    assert BriefVault(service).fragment("draft", "draft", fragment["id"])["fragment"]["text"] == "Exact full source"


def test_stale_human_intent_never_applies_and_reject_is_replayable(setup):
    _, service, _ = setup
    seed(service)
    fragment = invoke(service, {"op": "create", "title": "Source", "text": "Text", "discipline": "be", "scopeNodeId": ""}, "create")["result"]["fragment"]
    pending = invoke(service, {"op": "set-mvp", "fragmentIds": [fragment["id"]], "mvp": "yes"}, "mvp")
    invoke(service, {"op": "revise", "fragmentId": fragment["id"], "expectedRevision": 1, "note": "New source", "text": "New"}, "revise")
    with pytest.raises(NextStep, match="changed"):
        ops.decide(service, "draft", "draft", "mvp", pending["result"]["digest"], "accept", "human")
    result = ops.decide(service, "draft", "draft", "mvp", pending["result"]["digest"], "reject", "human")
    assert result["status"] == "rejected"
    assert ops.decide(service, "draft", "draft", "mvp", pending["result"]["digest"], "reject", "human") == result


def test_native_commit_then_lost_readback_retains_pending_and_never_repeats(setup, monkeypatch):
    _, service, _ = setup
    seed(service)
    command = {"op": "create", "title": "Source", "text": "Text", "discipline": "be", "scopeNodeId": ""}
    def fail(*args):
        raise RuntimeError("Lost readback after native commit")
    monkeypatch.setattr(ops, "verify_result", fail)
    with pytest.raises(NextStep, match="lost.*uncertain"):
        invoke(service, command, "lost")
    with pytest.raises(NextStep, match="incomplete"):
        invoke(service, command, "lost")
    count = service.db_for("draft").execute("SELECT COUNT(*) FROM brief_fragment_revisions WHERE project_id='draft' AND workspace_id='draft'").fetchone()[0]
    assert count == 1
