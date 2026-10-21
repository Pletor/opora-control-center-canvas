"""The pure semantic projector composes with bounded SQLite journal replay."""
import sqlite3

import pytest

from backend.canvas.graph import encode
from backend.canvas.test_graph_card import node
from backend.editor.agent_memory.desktop_v3_state import default_state
from backend.editor.agent_packet.specification_sql_context import (
    project_sql_context,
    sql_context_digest,
)
from database.repositories.opora_context_events import enroll
from database.repositories.opora_context_replay import replay
from database.repositories.opora_context_snapshot import capture
from database.repositories.workspace_graph_authority import WorkspaceGraphAuthority
from database.schema.project_initialization import initialize_project_schema

PROJECT = WORKSPACE = "draft"
TARGET = "target"
META = {"id": PROJECT, "name": "Local project"}


def database():
    db = sqlite3.connect(":memory:")
    initialize_project_schema(db)
    db.commit()
    db.execute("BEGIN IMMEDIATE")
    graph = {"nodes": [node("parent", "sector"), node(TARGET, parent_id="parent"),
                       node("other")], "edges": []}
    WorkspaceGraphAuthority(db, PROJECT, WORKSPACE).enroll(graph)
    state = default_state()
    state["nodes"][TARGET] = {"phase": "discover", "criteria": [], "steps": [], "actions": [],
                              "rules": [{"id": "instruction", "text": "A", "kind": "must"}]}
    state["nodes"]["other"] = {"phase": "discover", "criteria": [], "steps": [], "actions": [],
                                "rules": [{"id": "other-rule", "text": "Unrelated A", "kind": "must"}]}
    db.execute("INSERT INTO desktop_v3_state VALUES(?,?,?,?,?)",
               (PROJECT, WORKSPACE, 1, encode(state), "now"))
    enroll(db, PROJECT)
    return db, state


def projector(rows):
    return project_sql_context(rows, PROJECT, WORKSPACE, TARGET, metadata=META)


def test_unrelated_card_text_and_instruction_updates_pass_replay():
    db, state = database()
    try:
        origin = capture(db, PROJECT)
        db.execute("INSERT INTO node_text_revisions VALUES(?,?,?,?,?,?)",
                   (PROJECT, WORKSPACE, "other", 1, "Unrelated text", "now"))
        state["nodes"]["other"]["rules"][0]["text"] = "Unrelated B"
        db.execute("UPDATE desktop_v3_state SET revision=2,state=? WHERE project_id=? AND workspace_id=?",
                   (encode(state), PROJECT, WORKSPACE))
        result = replay(db, origin, projector)
        assert result["liveScopeUnchanged"] is True
        assert result["transitionCount"] == 2
    finally:
        db.close()


def test_relevant_instruction_aba_has_equal_endpoint_projection_but_fails():
    db, state = database()
    try:
        origin = capture(db, PROJECT)
        original_digest = sql_context_digest(origin["rows"], PROJECT, WORKSPACE, TARGET, metadata=META)
        state["nodes"][TARGET]["rules"][0]["text"] = "B"
        db.execute("UPDATE desktop_v3_state SET revision=2,state=? WHERE project_id=? AND workspace_id=?",
                   (encode(state), PROJECT, WORKSPACE))
        state["nodes"][TARGET]["rules"][0]["text"] = "A"
        db.execute("UPDATE desktop_v3_state SET revision=3,state=? WHERE project_id=? AND workspace_id=?",
                   (encode(state), PROJECT, WORKSPACE))
        current = capture(db, PROJECT)
        assert sql_context_digest(current["rows"], PROJECT, WORKSPACE, TARGET, metadata=META) == original_digest
        assert project_sql_context(current["rows"], PROJECT, WORKSPACE, TARGET, metadata=META) == projector(origin["rows"])
        with pytest.raises(ValueError, match="scope changed"):
            replay(db, origin, projector)
    finally:
        db.close()
