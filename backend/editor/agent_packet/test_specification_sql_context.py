"""Private SQL semantics match readers while excluding unrelated mutable state."""
import copy
import json

import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.graph import encode
from backend.canvas.test_graph_card import node
from backend.editor.agent_memory.desktop_v3_state import default_state
from backend.editor.agent_packet.desktop_v3_packets import redact_deep
from backend.editor.agent_packet.specification_context import capture_specification
from backend.editor.agent_packet.specification_sql_context import (
    project_sql_context,
    sql_context_digest,
)
from backend.editor.node.node_specs import EMPTY_FIELDS
from database.repositories.opora_context_events_sources import SOURCES
from database.repositories.workspace_graph_authority import WorkspaceGraphAuthority, _encode

META = {"id": "draft", "name": "Local project"}


def fixture():
    rows = {table: [] for table in SOURCES}
    graph = {"nodes": [node("parent", "sector"), node("target", parent_id="parent"), node("other")], "edges": []}
    graph_raw, fingerprint = _encode(graph)
    rows["workspace_graph_authority"] = [{"project_id": "draft", "workspace_id": "draft",
        "revision": 1, "graph": graph_raw, "digest": fingerprint}]
    return rows


def projected(rows):
    return project_sql_context(rows, "draft", "draft", "target", metadata=META)


def fingerprint(rows):
    return sql_context_digest(rows, "draft", "draft", "target", metadata=META)


def put(rows, table, **fields):
    defaults = {"project_id": "draft", "workspace_id": "draft", "revision": 1, "saved_at": "now"}
    row = {key: fields.get(key, defaults.get(key, "")) for key in SOURCES[table]}
    rows[table].append(row)
    return row


def mutate_graph(rows, change):
    authority = rows["workspace_graph_authority"][0]
    graph = json.loads(authority["graph"])
    change(graph)
    authority["graph"], authority["digest"] = _encode(graph)
    authority["revision"] += 1


def test_real_capture_reader_parity_for_ordinary_selected_content(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    try:
        rows = fixture()
        graph = json.loads(rows["workspace_graph_authority"][0]["graph"])
        canvas.save_graph("draft", "draft", graph, canvas.view("draft", "draft")["digest"])
        db = canvas.db_for("draft")
        with canvas.lock_for("draft"), db:
            db.execute("BEGIN IMMEDIATE")
            WorkspaceGraphAuthority(db, "draft", "draft").enroll(graph)
            db.execute("INSERT INTO project_settings VALUES('draft',3,'Project goal','app')")
            db.execute("INSERT INTO project_profile VALUES('draft','modular','multi')")
            canvas.specs.save_in_transaction(("draft", "draft", "target"), 0, {**EMPTY_FIELDS, "goal": "Goal"})
            db.execute("INSERT INTO node_text_revisions VALUES('draft','draft','target',1,'Article','now')")
            db.execute("INSERT INTO drawing_revisions VALUES('draft','draft','target',1,?, 'now')", (encode({"elements": []}),))
        rows = {table: [dict(row) for row in db.execute(f'SELECT * FROM "{table}" WHERE project_id=?', ("draft",))]
                for table in SOURCES}
        actual = capture_specification(canvas, "draft", "draft", "target")["specification"]
        selected = projected(rows)
        for key in ("cards", "rules", "settings", "decisions", "project"):
            assert selected[key] == actual[key] if key != "project" else selected[key]["settings"] == actual[key]["settings"]
        assert [{k: v for k, v in drawing.items() if k != "workspace"} for drawing in selected["drawings"]] == actual["drawings"]
    finally:
        canvas.close()


def test_architecture_document_owner_redirect_is_explicit():
    rows = fixture()
    arch = {"nodes": [node("app", "sector", site={"kind": "application", "environments": []})], "edges": []}
    put(rows, "project_architecture", graph=encode(arch), removed=encode({"nodes": [], "edges": []}))
    mutate_graph(rows, lambda g: g["nodes"][0].update(parentId="app"))
    put(rows, "node_text_revisions", node_id="app", workspace_id="architecture", text="Shared text")
    put(rows, "node_text_revisions", node_id="app", text="Wrong owner")
    put(rows, "node_spec_revisions", node_id="app", workspace_id="architecture", fields=encode({**EMPTY_FIELDS, "goal": "Shared goal"}))
    value = projected(rows)
    document = next(card for card in value["cards"] if card["nodeId"] == "app")
    assert document["content"]["text"] == "Shared text"
    assert document["spec"]["fields"]["goal"] == "Shared goal"
    assert {"nodeId": "app", "specWorkspace": "architecture", "textWorkspace": "architecture"} in value["owners"]


@pytest.mark.parametrize("table,fields", [
    ("node_text_revisions", {"node_id": "target", "text": "Changed"}),
    ("node_spec_revisions", {"node_id": "target", "fields": encode({**EMPTY_FIELDS, "goal": "Changed"})}),
    ("drawing_revisions", {"layer_id": "target", "scene": encode({"elements": []})}),
])
def test_relevant_content_changes_digest(table, fields):
    rows = fixture()
    original = fingerprint(rows)
    put(rows, table, **fields)
    assert fingerprint(rows) != original


def test_unrelated_content_state_saved_at_and_raw_revisions_are_ignored():
    rows = fixture()
    original = fingerprint(rows)
    put(rows, "node_text_revisions", node_id="other", text="Unrelated")
    put(rows, "drawing_revisions", layer_id="other", scene=encode({"elements": []}))
    state = default_state()
    state["nodes"]["other"] = {"phase": "discover", "criteria": [], "steps": []}
    put(rows, "desktop_v3_state", revision=77, state=encode(state), saved_at="later")
    mutate_graph(rows, lambda g: g["nodes"][-1].update(name="Renamed unrelated"))
    assert fingerprint(rows) == original


def test_raw_secrets_differ_despite_equal_public_redaction():
    rows = fixture()
    text = put(rows, "node_text_revisions", node_id="target", text="api_key=sk-" + "a" * 45)
    first = projected(rows)
    text["text"] = "api_key=sk-" + "b" * 45
    second = projected(rows)
    assert first != second
    assert redact_deep(first) == redact_deep(second)


def test_secret_shaped_rule_ids_do_not_hide_raw_task_instructions():
    rows = fixture()
    state = default_state()
    state["rules"] = [{"id": "ghp_" + "a" * 36, "text": "Must test", "kind": "must",
                       "scope": "project", "target": ""}]
    state["nodes"]["target"] = {"phase": "discover", "criteria": [], "steps": [],
                                  "actions": [], "rules": [{"id": "instruction", "text": "Read", "kind": "must"}]}
    row = put(rows, "desktop_v3_state", state=encode(state))
    original = fingerprint(rows)
    assert projected(rows)["rules"] == state["rules"]
    state["rules"][0]["text"] = "Must verify"
    row["state"] = encode(state)
    changed = fingerprint(rows)
    assert changed != original
    state["nodes"]["target"]["rules"][0]["text"] = "Read twice"
    row["state"] = encode(state)
    assert fingerprint(rows) != changed


def test_predecessor_sector_completion_changes_private_eligibility():
    rows = fixture()
    mutate_graph(rows, lambda g: (g["nodes"].extend([node("prior", "sector"), node("member", parent_id="prior")]),
                                 g["edges"].append({"id": "before", "source": "prior", "target": "parent"})))
    original = projected(rows)
    assert original["eligibility"]["blockers"] == [{"id": "prior", "name": "prior"}]
    state = default_state()
    state["nodes"]["member"] = {"phase": "discover", "criteria": [], "steps": [],
                                  "done": {"confirmed": True, "at": "2026-10-21T00:00:00Z", "by": "human", "note": ""}}
    put(rows, "desktop_v3_state", state=encode(state))
    changed = projected(rows)
    assert changed["eligibility"]["blockers"] == []
    assert changed != original


@pytest.mark.parametrize("change", [
    lambda g: g["nodes"].append(node("child", parent_id="target")),
    lambda g: g["edges"].append({"id": "new-edge", "source": "other", "target": "target"}),
    lambda g: g["nodes"].append(node("area", "area", parent_id="parent", size={"w": 500, "h": 500})),
])
def test_negative_graph_predicates_change_projection(change):
    rows = fixture()
    original = fingerprint(rows)
    mutate_graph(rows, change)
    assert fingerprint(rows) != original


@pytest.mark.parametrize("corrupt", [
    lambda r: r["workspace_graph_authority"].clear(),
    lambda r: r["workspace_graph_authority"][0].update(digest="wrong"),
    lambda r: r["workspace_graph_authority"].append(copy.deepcopy(r["workspace_graph_authority"][0])),
    lambda r: put(r, "desktop_v3_state", state='{"nodes":{},"nodes":{}}'),
    lambda r: put(r, "node_spec_revisions", node_id="target", fields="[]"),
])
def test_malformed_sources_fail_closed(corrupt):
    rows = fixture()
    corrupt(rows)
    with pytest.raises((ValueError, TypeError)):
        projected(rows)
