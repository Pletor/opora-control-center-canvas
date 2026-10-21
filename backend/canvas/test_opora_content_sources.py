"""Native content-source capture and transaction-safe acceptance writes."""
import copy
import json

import pytest

from backend.canvas.opora_content_sources import (
    before_precondition,
    capture_content,
    preview_config_changes,
    read_entry,
    write_changes_in_transaction,
)
from backend.canvas.test_opora_graph_initial import empty_graphs as empty_graphs  # noqa: PLC0414
from backend.canvas.test_opora_graph_proposals import accept, proposal
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State, default_state
from backend.editor.agent_memory.input_security import security_block


def prepared(graphs):
    item = proposal(graphs, plan={"nodes": [
        {"ref": "sector", "kind": "sector", "name": "Plan"},
        {"ref": "task", "kind": "node", "parent": "sector", "name": "Task"},
        {"ref": "other", "kind": "node", "parent": "sector", "name": "Other"},
    ]})
    accept(graphs, item)
    return graphs.service, item["refs"]


def block(*, status="open", note="", todo_done=False):
    return {"id": "b1", "number": "1", "title": "Block", "text": "Before", "tags": [],
            "todos": [{"id": "t1", "text": "Check", "done": todo_done, "assignee": ""}], "images": [],
            "state": {"status": status, "note": note, "condition": "", "onMet": {"kind": "none", "targetId": "", "note": ""},
                       "onUnmet": {"kind": "none", "targetId": "", "note": ""}}, "parentBlockId": ""}


def seed_state(service, node_id, *, round_number=3):
    state = default_state()
    state["nodes"][node_id] = {"phase": "build", "criteria": [], "steps": [], "round": {
        "number": round_number, "openedAt": "2026-01-01T00:00:00+00:00", "by": "human", "reason": "new work"},
        "actions": [], "rules": [], "blocks": [block(status="met", note="Keep progress", todo_done=True)],
        "materials": []}
    db = service.db_for("draft")
    db.execute("INSERT OR REPLACE INTO desktop_v3_state VALUES(?,?,?,?,?)",
               ("draft", "draft", 1, json.dumps(state), "now"))
    db.commit()
    service.read_cache.drop("draft")
    return state


def test_capture_uses_text_owner_and_complete_root_card_content(empty_graphs):
    service, refs = prepared(empty_graphs)
    seed_state(service, refs["task"])
    db = service.db_for("draft")
    db.execute("INSERT INTO node_text_revisions VALUES(?,?,?,?,?,?)",
               ("draft", "draft", refs["task"], 1, "Task text", "now"))
    entries, observations = capture_content(service, "draft", "draft", service.view("draft", "draft")["graph"])
    assert len(entries) == 3 * 7 + 1
    assert entries == sorted(entries, key=lambda item: (item["kind"], item["target"], item["field"]))
    text = next(item for item in entries if item["kind"] == "text" and item["target"] == refs["task"])
    assert text["ownerWorkspace"] == "draft" and text["revision"] == 1 and text["value"] == "Task text"
    assert ("drawing", "", "scene") in observations
    config = next(item for item in entries if item["kind"] == "config" and item["target"] == refs["task"] and item["field"] == "blocks")
    assert "status" not in config["value"][0]["state"] and "note" not in config["value"][0]["state"]
    assert "done" not in config["value"][0]["todos"][0]
    assert "round" not in json.dumps(config)
    assert observations[("config", refs["task"], "actions")]["round"] == 3


def test_config_write_merges_independent_live_field_and_preserves_progress(empty_graphs):
    service, refs = prepared(empty_graphs)
    before_state = seed_state(service, refs["task"])
    actions_before = before_precondition(service, "draft", "draft", "config", refs["task"], "actions")
    blocks_before = before_precondition(service, "draft", "draft", "config", refs["task"], "blocks")
    live = copy.deepcopy(before_state)
    live["nodes"][refs["task"]]["rules"] = [{"id": "r1", "text": "Concurrent unrelated edit", "kind": "must"}]
    live["nodes"][refs["task"]]["phase"] = "verify"
    live["nodes"][refs["task"]]["blocks"][0]["state"]["note"] = "Latest progress"
    live["nodes"][refs["task"]]["blocks"][0]["todos"][0]["done"] = False
    db = service.db_for("draft")
    db.execute("UPDATE desktop_v3_state SET revision=2,state=? WHERE project_id='draft' AND workspace_id='draft'",
               (json.dumps(live),))
    db.commit()
    service.read_cache.drop("draft")
    desired_actions = [{"id": "a1", "pipelineId": "build", "label": "Build", "params": {}}]
    desired_blocks = copy.deepcopy(blocks_before["value"])
    desired_blocks[0]["text"] = "Accepted instruction"
    changes = [
        {**actions_before, "observedRound": 3, "before": actions_before["value"], "value": desired_actions},
        {**blocks_before, "observedRound": 3, "before": blocks_before["value"], "value": desired_blocks},
    ]
    with db:
        db.execute("BEGIN IMMEDIATE")
        write_changes_in_transaction(service, db, "draft", "draft", changes, actor="human",
                                     graph=service.view("draft", "draft")["graph"])
        assert db.in_transaction
    stored = DesktopV3State(service).current("draft", "draft")["state"]["nodes"][refs["task"]]
    assert stored["rules"] == live["nodes"][refs["task"]]["rules"] and stored["phase"] == "verify"
    assert stored["round"] == live["nodes"][refs["task"]]["round"]
    assert stored["blocks"][0]["state"]["status"] == "met"
    assert stored["blocks"][0]["state"]["note"] == "Latest progress"
    assert stored["blocks"][0]["todos"][0]["done"] is False
    assert stored["blocks"][0]["text"] == "Accepted instruction"


def test_text_revision_conflict_and_rollback_leave_sources_unchanged(empty_graphs):
    service, refs = prepared(empty_graphs)
    db = service.db_for("draft")
    db.execute("INSERT INTO node_text_revisions VALUES(?,?,?,?,?,?)",
               ("draft", "draft", refs["task"], 1, "Before", "now"))
    db.commit()
    pre = before_precondition(service, "draft", "draft", "text", refs["task"], "text")
    db.execute("INSERT INTO node_text_revisions VALUES(?,?,?,?,?,?)",
               ("draft", "draft", refs["task"], 2, "Concurrent", "now"))
    db.commit()
    change = {**pre, "observedRevision": 1, "before": "Before", "value": "Accepted"}
    with db:
        db.execute("BEGIN IMMEDIATE")
        with pytest.raises(ValueError, match="revision changed"):
            write_changes_in_transaction(service, db, "draft", "draft", [change], actor="human",
                                         graph=service.view("draft", "draft")["graph"])
        db.rollback()
    assert read_entry(service, "draft", "draft", "text", refs["task"], "text")["value"] == "Concurrent"


def test_config_preview_is_pure_and_preserves_block_progress(empty_graphs):
    service, refs = prepared(empty_graphs)
    source = seed_state(service, refs["task"])
    original = copy.deepcopy(source)
    block_entry = before_precondition(service, "draft", "draft", "config", refs["task"], "blocks")
    desired = copy.deepcopy(block_entry["value"])
    desired[0]["text"] = "Preview"
    state = preview_config_changes(source, [{"kind": "config", "target": refs["task"],
        "field": "blocks", "value": desired}], service.view("draft", "draft")["graph"])
    assert source == original
    updated = state["nodes"][refs["task"]]["blocks"][0]
    assert updated["text"] == "Preview" and updated["state"]["status"] == "met"
    assert updated["state"]["note"] == "Keep progress" and updated["todos"][0]["done"] is True


def test_native_write_rejects_changed_card_round(empty_graphs):
    service, refs = prepared(empty_graphs)
    seed_state(service, refs["task"])
    db = service.db_for("draft")
    pre = before_precondition(service, "draft", "draft", "text", refs["task"], "text")
    state = DesktopV3State(service).current("draft", "draft")["state"]
    state["nodes"][refs["task"]]["round"]["number"] = 4
    db.execute("UPDATE desktop_v3_state SET revision=2,state=? WHERE project_id='draft' AND workspace_id='draft'",
               (json.dumps(state),))
    db.commit()
    service.read_cache.drop("draft")
    change = {**pre, "observedRound": 3, "before": "", "value": "Accepted"}
    with db:
        db.execute("BEGIN IMMEDIATE")
        with pytest.raises(ValueError, match="round changed"):
            write_changes_in_transaction(service, db, "draft", "draft", [change], actor="human",
                                         graph=service.view("draft", "draft")["graph"])
        db.rollback()


def test_confirmed_card_config_matches_native_closed_block_guard(empty_graphs):
    service, refs = prepared(empty_graphs)
    state = seed_state(service, refs["task"])
    node = state["nodes"][refs["task"]]
    node["done"] = {"confirmed": True, "at": "2026-01-01T00:00:00+00:00", "by": "human", "note": ""}
    db = service.db_for("draft")
    db.execute("UPDATE desktop_v3_state SET state=? WHERE project_id='draft' AND workspace_id='draft'", (json.dumps(state),))
    db.commit()
    graph = service.view("draft", "draft")["graph"]
    same = preview_config_changes(state, [{"kind": "config", "target": refs["task"],
        "field": "blocks", "value": before_precondition(service, "draft", "draft", "config", refs["task"], "blocks")["value"]}], graph)
    assert same["nodes"][refs["task"]]["blocks"] == node["blocks"]
    changed = copy.deepcopy(before_precondition(service, "draft", "draft", "config", refs["task"], "blocks")["value"])
    changed[0]["text"] = "Changed while closed"
    with pytest.raises(ValueError, match="reopen the card"):
        preview_config_changes(state, [{"kind": "config", "target": refs["task"], "field": "blocks", "value": changed}], graph)
    reopened = copy.deepcopy(state)
    reopened["nodes"][refs["task"]]["done"]["confirmed"] = False
    result = preview_config_changes(reopened, [{"kind": "config", "target": refs["task"], "field": "blocks", "value": changed}], graph)
    assert result["nodes"][refs["task"]]["blocks"][0]["text"] == "Changed while closed"
    assert result["nodes"][refs["task"]]["blocks"][0]["state"]["note"] == "Keep progress"


def test_downloads_url_security_block_is_validated_by_native_state(empty_graphs):
    service, refs = prepared(empty_graphs)
    state = default_state()
    graph = service.view("draft", "draft")["graph"]
    target = refs["task"]
    security = security_block(1)
    changes = [
        {"kind": "config", "target": target, "field": "downloadsUrl", "value": True},
        {"kind": "config", "target": target, "field": "blocks", "value":[{
            key: value for key, value in security.items() if key != "state"
        } | {"state": {key: value for key, value in security["state"].items() if key not in {"status", "note"}}}]},
    ]
    result = preview_config_changes(state, changes, graph)
    assert result["nodes"][target]["downloadsUrl"] is True
    with pytest.raises(ValueError, match="input-security"):
        preview_config_changes(state, [changes[0]], graph)
