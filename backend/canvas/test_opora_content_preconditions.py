"""Independent configuration fields, round/owner guards and canonical architecture text."""
import json

import pytest

from backend.canvas.opora_content_changes import OporaContentChanges
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.test_opora_changesets import AGENT, SCOPE, baseline
from backend.canvas.test_opora_changesets import service as service  # noqa: PLC0414
from backend.canvas.test_opora_content_changes import accepted, change, propose
from backend.canvas.test_opora_execution_context import sparse as sparse  # noqa: PLC0414
from backend.canvas.test_opora_graph_initial import empty_graphs as empty_graphs  # noqa: PLC0414
from backend.editor.agent_memory.desktop_v3_state import default_state


def test_independent_config_fields_rebase_preserves_latest_working_progress(sparse):
    _, authority, refs = sparse
    first = propose(sparse, [change("config", refs["a"], "rules", [{"id": "r", "text": "Test", "kind": "must"}])])
    second = propose(sparse, [change("config", refs["a"], "actions", [{"id": "act", "pipelineId": "build", "label": "Build", "params": {}}])])
    head = accepted(sparse, first)
    db = authority.canvas.db_for("draft")
    row = db.execute("SELECT state FROM desktop_v3_state WHERE project_id='draft' AND workspace_id='draft'").fetchone()
    state = json.loads(row[0])
    state["nodes"][refs["a"]]["phase"] = "define"
    with db:
        db.execute("UPDATE desktop_v3_state SET revision=revision+1,state=? WHERE project_id='draft' AND workspace_id='draft'", (json.dumps(state),))
    moved = OporaContentChanges(authority.canvas).rebase(second["id"], {**SCOPE, "expectedAcceptedHead": head["id"]}, AGENT)
    assert moved["conflicts"] == []
    accepted(sparse, moved["proposal"])
    node = json.loads(db.execute("SELECT state FROM desktop_v3_state WHERE project_id='draft' AND workspace_id='draft'").fetchone()[0])["nodes"][refs["a"]]
    assert node["phase"] == "define" and node["rules"][0]["text"] == "Test" and node["actions"][0]["label"] == "Build"


def test_card_round_change_is_explicit_rebase_conflict(sparse):
    _, authority, refs = sparse
    item = propose(sparse, [change("text", refs["a"], "text", "Round-bound text")])
    state = default_state()
    state["nodes"][refs["a"]] = {"phase": "discover", "criteria": [], "steps": [], "round": {
        "number": 2, "openedAt": "2026-10-21T00:00:00Z", "by": "human", "reason": "New round"}}
    with authority.canvas.db_for("draft") as db:
        db.execute("INSERT INTO desktop_v3_state VALUES(?,?,?,?,?)", ("draft", "draft", 1, json.dumps(state), "now"))
    with pytest.raises(ValueError, match="preconditions"):
        accepted(sparse, item)
    rebased = OporaContentChanges(authority.canvas).rebase(item["id"], {**SCOPE, "expectedAcceptedHead": item["parentRevision"]}, AGENT)
    assert rebased["conflicts"] and rebased["proposal"] is None


def test_v1_assignment_and_accepted_manifest_use_same_architecture_text_owner(service):
    baseline(service)
    with service.lock_for("draft"), service.db_for("draft") as db:
        db.execute("BEGIN IMMEDIATE")
        service.texts.save_in_transaction(("draft", "architecture", "page"), 0, "Shared architecture article")
        service.texts.save_in_transaction(("draft", "draft", "page"), 0, "Wrong workspace copy")
    sparse = (None, ExecutionResults(service), {"a": "a"})
    accepted(sparse, propose(sparse, [change("text", "a", "text", "Accepted ordinary text")]))
    context = sparse[1].context(**SCOPE, node="page")
    assert context["available"], context
    record = sparse[1].claim({**SCOPE, "nodeId": "page", "requestId": "architecture", "ttlSeconds": 60,
        "expectedAcceptedHead": context["acceptedHead"], "expectedContextVersion": context["contextVersion"]}, "agent:worker")
    card = next(item for item in record["assignment"]["specification"]["cards"] if item["nodeId"] == "page")
    assert card["content"]["text"] == "Shared architecture article"
