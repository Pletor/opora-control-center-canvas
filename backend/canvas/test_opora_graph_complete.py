"""Complete pending plans preserve content and accept through one native transaction."""
from copy import deepcopy

import pytest

from backend.canvas.test_opora_graph_changes import approve, edits
from backend.canvas.test_opora_graph_proposals import graphs, proposal, service
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from database.repositories.opora_changesets import ChangesetRepository

__all__ = ["edits", "graphs", "service"]


def full_plan():
    return {"nodes": [{"ref": "source", "kind": "node", "name": "Source", "text": "Exact proposed text",
                        "spec": {"goal": "Reviewed goal"},
                        "blocks": [{"ref": "proof", "title": "Proof", "ports": [{"ref": "ready", "label": "Ready"}]}]},
                       {"ref": "target", "kind": "node", "name": "Target"}],
            "edges": [{"from": "source", "to": "target", "port": "block", "block": "proof", "blockPort": "ready"}]}


def test_full_pending_reload_keeps_authority_and_content_unchanged(edits, service):
    before = deepcopy(service.view("draft", "draft"))
    state = deepcopy(DesktopV3State(service).current("draft", "draft"))
    head = edits.context("draft", "draft")["acceptedHead"]
    item = proposal(edits, plan=full_plan())
    saved = edits.read("draft", "draft", item["id"])
    assert saved == item and saved["schemaVersion"] == 3 and not saved["accepted"]
    assert service.view("draft", "draft")["graph"] == before["graph"]
    assert DesktopV3State(service).current("draft", "draft") == state
    assert edits.context("draft", "draft")["acceptedHead"] == head
    source = item["refs"]["source"]
    assert service.texts.read(("draft", "draft", source))["revision"] == 0
    assert saved["contentEffects"]["after"]["nodes"][source]["blocks"][0]["ports"][0]["id"] == "ready"
    result = approve(edits, item)
    assert service.texts.read(("draft", "draft", source))["text"] == "Exact proposed text"
    assert service.specs.read(("draft", "draft", source))["fields"]["goal"] == "Reviewed goal"
    assert service.view("draft", "draft")["graph"] == item["resultGraph"]
    assert DesktopV3State(service).current("draft", "draft")["state"] == item["contentEffects"]["after"]
    assert approve(edits, item) == result
    assert service.texts.read(("draft", "draft", source))["revision"] == 1


def test_complete_acceptance_rolls_back_graph_state_text_and_specs(edits, service, monkeypatch):
    item = proposal(edits, plan=full_plan())
    before = deepcopy(service.view("draft", "draft"))
    state = deepcopy(DesktopV3State(service).current("draft", "draft"))
    head = edits.context("draft", "draft")["acceptedHead"]
    def fail(*args):
        raise RuntimeError("injected accepted-reference failure")
    monkeypatch.setattr(ChangesetRepository, "advance", fail)
    with pytest.raises(RuntimeError, match="injected"):
        approve(edits, item)
    assert service.view("draft", "draft")["graph"] == before["graph"]
    assert DesktopV3State(service).current("draft", "draft") == state
    assert edits.context("draft", "draft")["acceptedHead"] == head
    for node in item["refs"].values():
        assert service.texts.read(("draft", "draft", node))["revision"] == 0
        assert service.specs.read(("draft", "draft", node))["revision"] == 0


def test_invalid_pending_block_port_leaves_no_proposal(edits):
    plan = full_plan()
    plan["edges"][0]["blockPort"] = "absent"
    before = edits.list("draft", "draft")
    with pytest.raises(ValueError):
        proposal(edits, plan=plan)
    assert edits.list("draft", "draft") == before


def test_extend_native_documents_blocks_and_graph_fields_with_cas(edits, service):
    revision = DesktopV3State(service).current("draft", "draft")["revision"]
    spec_revision = service.specs.read(("draft", "draft", "a"))["revision"]
    plan = {"extend": [{"node": "@a", "expectedRevision": revision,
        "text": {"expectedRevision": 0, "text": "Extended text"},
        "spec": {"expectedRevision": spec_revision, "fields": {"goal": "Extended goal"}},
        "blocks": [{"ref": "proof", "title": "Proof", "ports": [{"ref": "ready"}]}]}],
        "edges": [{"from": "@a", "to": "@b", "port": "block", "block": "proof", "blockPort": "ready"}]}
    item = proposal(edits, plan=plan)
    assert service.texts.read(("draft", "draft", "a"))["revision"] == 0
    approve(edits, item)
    assert service.texts.read(("draft", "draft", "a"))["text"] == "Extended text"
    assert service.specs.read(("draft", "draft", "a"))["fields"]["goal"] == "Extended goal"
    with pytest.raises(ValueError, match="expectedRevision"):
        proposal(edits, plan=plan)


def test_stale_text_does_not_overwrite_or_auto_rebase(edits, service):
    revision = DesktopV3State(service).current("draft", "draft")["revision"]
    item = proposal(edits, plan={"extend": [{"node": "@a", "expectedRevision": revision,
        "text": {"expectedRevision": 0, "text": "Proposed"}}]})
    with service.db_for("draft"):
        service.texts.save_in_transaction(("draft", "draft", "a"), 0, "Concurrent edit")
    with pytest.raises(ValueError, match="revision"):
        approve(edits, item)
    assert service.texts.read(("draft", "draft", "a"))["text"] == "Concurrent edit"
    assert not edits.read("draft", "draft", item["id"])["accepted"]


def test_metadata_and_native_graph_edit_are_pending(edits, service):
    plan = {"draftVersion": 3, "nodes": [{"ref": "area", "kind": "area", "name": "Logic", "briefGroup": "logika", "size": {"w": 600, "h": 400}},
        {"ref": "sector", "kind": "sector", "name": "UX", "briefDiscipline": "ux"}],
        "updateNodes": [{"id": "a", "fields": {"name": "Reviewed name"}}]}
    item = proposal(edits, plan=plan)
    assert next(node for node in service.view("draft", "draft")["graph"]["nodes"] if node["id"] == "a")["name"] != "Reviewed name"
    approve(edits, item)
    state = DesktopV3State(service).current("draft", "draft")["state"]
    assert state["nodes"][item["refs"]["area"]]["briefGroup"] == "logika"
    assert state["nodes"][item["refs"]["sector"]]["briefDiscipline"] == "ux"


def test_missing_fragment_and_foreign_architecture_fail_without_mutation(edits, service):
    head = edits.context("draft", "draft")["acceptedHead"]
    with pytest.raises(ValueError):
        proposal(edits, plan={"nodes": [{"ref": "a", "kind": "node", "name": "A", "fragmentRef": {"fragmentId": "absent"}}]})
    assert edits.context("draft", "draft")["acceptedHead"] == head

