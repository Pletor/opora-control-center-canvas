import sqlite3

import pytest

from backend.flow.conftest import edge, node
from backend.flow.graph_check import FlowInvalid
from backend.flow.workflows import (
    FlowConflict, FlowNotFound, activate, approve, create_draft, create_workflow, get_version, list_workflows, reject,
    rollback, set_candidate,
)
from database.schema.project_schema import ensure_flow_owner_ref

GRAPH = {"nodes": [node("t", "trigger.manual"), node("e", "debug.echo")], "edges": [edge("1", "t", "e")]}


def promote(db, wid, graph=GRAPH):
    version = create_draft(db, wid, graph)
    set_candidate(db, version["id"])
    return activate(db, version["id"])


def test_shared_and_project_workflows(db):
    db.execute("INSERT INTO projects(id,name) VALUES('p','P')")
    shared = create_workflow(db, "heart", "Srdce")
    own = create_workflow(db, "page_intent", "Záměr", project_id="p", owner_ref="opora:page:n1")
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


INTENT = {"nodes": [node("in", "intent.entry"), node("ok", "intent.done")], "edges": [edge("1", "in", "ok")]}


def test_owner_ref_rules_and_lookup(db):
    db.execute("INSERT INTO projects(id,name) VALUES('p','P')")
    for kind, project, owner in (("page_intent", "p", None), ("page_intent", "p", "stránka"),
                                 ("page_intent", None, "opora:page:n1"), ("heart", None, "opora:page:n1")):
        with pytest.raises(FlowInvalid):
            create_workflow(db, kind, "X", project_id=project, owner_ref=owner)
    page = create_workflow(db, "page_intent", "Záměr", project_id="p", owner_ref="opora:page:n1")
    with pytest.raises(FlowConflict) as taken:
        create_workflow(db, "page_intent", "Jiný", project_id="p", owner_ref="opora:page:n1")
    assert taken.value.code == "owner_taken"
    create_workflow(db, "heart", "Srdce")
    create_workflow(db, "heart", "Srdce 2")  # NULL owner_ref jedinečnost nehlídá
    assert [w["id"] for w in list_workflows(db, "p", "page_intent", "opora:page:n1")] == [page["id"]]
    assert list_workflows(db, "p", owner_ref="opora:page:n2") == []


def test_page_intent_uses_its_catalog_and_human_approval(db):
    db.execute("INSERT INTO projects(id,name) VALUES('p','P')")
    wid = create_workflow(db, "page_intent", "Záměr", project_id="p", owner_ref="opora:page:n1")["id"]
    with pytest.raises(FlowInvalid):
        create_draft(db, wid, GRAPH)  # typy plátna 1 do záměru nepatří
    v1 = set_candidate(db, create_draft(db, wid, INTENT)["id"])
    with pytest.raises(FlowConflict) as refused:
        activate(db, v1["id"])
    assert refused.value.code == "approval_required"
    assert approve(db, v1["id"], "human")["status"] == "active"
    v2 = set_candidate(db, create_draft(db, wid, INTENT)["id"])
    with pytest.raises(FlowInvalid):
        reject(db, v2["id"], "  ", "human")
    assert reject(db, v2["id"], "chybí mapa", "human")["status"] == "retired"
    with pytest.raises(FlowConflict):
        reject(db, v2["id"], "znovu", "human")
    approve(db, set_candidate(db, create_draft(db, wid, INTENT)["id"])["id"], "human")
    assert rollback(db, wid)["id"] == v1["id"]  # zamítnutý v2 aktivní nikdy nebyl, návrat ho přeskočí
    heart = create_workflow(db, "heart", "Srdce")["id"]
    with pytest.raises(FlowConflict):
        approve(db, set_candidate(db, create_draft(db, heart, GRAPH)["id"])["id"], "human")


def test_owner_ref_migration_on_old_registry():
    old = sqlite3.connect(":memory:")
    old.execute("CREATE TABLE flow_workflows(id TEXT PRIMARY KEY, kind TEXT, project_id TEXT, name TEXT, "
                "created_at TEXT)")
    ensure_flow_owner_ref(old)
    ensure_flow_owner_ref(old)
    assert "owner_ref" in {row[1] for row in old.execute("PRAGMA table_info(flow_workflows)")}
    assert old.execute("SELECT 1 FROM sqlite_master WHERE name='flow_workflows_owner'").fetchone()


OLD_FLOW = """
CREATE TABLE flow_workflows(id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('heart','page_intent',
  'brain_workflow')), project_id TEXT, name TEXT NOT NULL, created_at TEXT NOT NULL, owner_ref TEXT);
CREATE TABLE flow_workflow_versions(id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL REFERENCES flow_workflows(id),
  n INTEGER NOT NULL, graph TEXT NOT NULL, hash TEXT NOT NULL, parent_version_id TEXT, status TEXT NOT NULL,
  eval_run_id TEXT, created_at TEXT NOT NULL, UNIQUE(workflow_id, n));
CREATE TRIGGER flow_workflow_versions_frozen BEFORE UPDATE OF id, workflow_id, n, graph, hash, parent_version_id
  ON flow_workflow_versions BEGIN SELECT RAISE(ABORT,'Verze workflow je neměnná'); END;
CREATE UNIQUE INDEX flow_workflows_owner ON flow_workflows(project_id, kind, owner_ref) WHERE owner_ref IS NOT NULL;
INSERT INTO flow_workflows VALUES('h','heart',NULL,'Srdce','2026-11-01',NULL);
INSERT INTO flow_workflow_versions VALUES('v','h',1,'{}','x',NULL,'active',NULL,'2026-11-01');
"""


def test_library_flow_migration_on_old_schema():
    old = sqlite3.connect(":memory:")
    old.row_factory = sqlite3.Row
    old.executescript(OLD_FLOW)
    ensure_flow_owner_ref(old)
    ensure_flow_owner_ref(old)
    assert [tuple(r) for r in old.execute("SELECT id, kind FROM flow_workflows")] == [("h", "heart")]
    assert get_version(old, "v")["derived_from"] is None
    with pytest.raises(sqlite3.IntegrityError):  # rodokmen je neměnný jako graf
        old.execute("UPDATE flow_workflow_versions SET derived_from='{}' WHERE id='v'")
    with pytest.raises(sqlite3.IntegrityError):
        old.execute("INSERT INTO flow_workflows(id,kind,name,created_at) VALUES('b','brain_workflow','B','t')")
    ref = "opora:library:human:ai-rag/rag"
    create_workflow(old, "library_flow", "RAG", owner_ref=ref)
    with pytest.raises(FlowConflict):  # NULL project_id: jedinečnost hlídá index s COALESCE
        create_workflow(old, "library_flow", "RAG 2", owner_ref=ref)
    assert old.execute("SELECT 1 FROM sqlite_master WHERE name='flow_library_folders'").fetchone()


def test_library_flow_owner_refs(db):
    db.execute("INSERT INTO projects(id,name) VALUES('p','P')")
    for project, owner in ((None, None), (None, "opora:library:robot:x/y"), (None, "opora:project-flow:n1"),
                           ("p", "opora:library:human:x/y")):
        with pytest.raises(FlowInvalid):
            create_workflow(db, "library_flow", "X", project_id=project, owner_ref=owner)
    assert create_workflow(db, "library_flow", "Kopie", "p", "opora:project-flow:n1")["project_id"] == "p"
