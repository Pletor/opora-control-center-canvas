import sqlite3

import pytest

from backend.flow.conftest import edge, node
from backend.flow.graph_check import FlowInvalid
from backend.flow.workflows import (
    FlowConflict, FlowNotFound, activate, create_draft, create_workflow, get_version, list_workflows, rollback,
    set_candidate,
)

GRAPH = {"nodes": [node("t", "trigger.manual"), node("e", "debug.echo")], "edges": [edge("1", "t", "e")]}


def promote(db, wid, graph=GRAPH):
    version = create_draft(db, wid, graph)
    set_candidate(db, version["id"])
    return activate(db, version["id"])


def test_shared_and_project_workflows(db):
    db.execute("INSERT INTO projects(id,name) VALUES('p','P')")
    shared = create_workflow(db, "heart", "Srdce")
    own = create_workflow(db, "page_intent", "Záměr", project_id="p")
    assert shared["project_id"] is None
    assert {w["id"] for w in list_workflows(db, "p")} == {shared["id"], own["id"]}
    assert [w["id"] for w in list_workflows(db, "jiny")] == [shared["id"]]
    with pytest.raises(FlowNotFound):
        create_workflow(db, "heart", "X", project_id="nikdo")
    with pytest.raises(FlowInvalid):
        create_workflow(db, "nic", "X")


def test_version_lifecycle_one_active_and_rollback(db):
    wid = create_workflow(db, "heart", "Srdce")["id"]
    v1 = promote(db, wid)
    v2 = promote(db, wid, {**GRAPH, "edges": []})
    assert v2["n"] == 2 and v2["parent_version_id"] == v1["id"]
    assert get_version(db, v1["id"])["status"] == "retired"
    assert v1["hash"] != v2["hash"]
    back = rollback(db, wid)
    assert back["id"] == v1["id"] and back["status"] == "active"
    assert get_version(db, v2["id"])["status"] == "retired"
    with pytest.raises(FlowConflict):
        rollback(db, wid)
    assert list_workflows(db)[0]["active_version_id"] == v1["id"]


def test_draft_rules_and_immutability(db):
    wid = create_workflow(db, "heart", "Srdce")["id"]
    draft = create_draft(db, wid, GRAPH)
    with pytest.raises(FlowConflict):
        activate(db, draft["id"])
    with pytest.raises(FlowInvalid):
        create_draft(db, wid, {"nodes": [node("x", "nope")], "edges": []})
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE flow_workflow_versions SET graph='{}' WHERE id=?", (draft["id"],))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("DELETE FROM flow_workflow_versions WHERE id=?", (draft["id"],))
    set_candidate(db, draft["id"])
    with pytest.raises(FlowConflict):
        set_candidate(db, draft["id"])
