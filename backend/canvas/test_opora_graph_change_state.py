"""Removal review is explicit, preserves history and never owns the transaction."""
from copy import deepcopy

import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.graph import encode
from backend.canvas.opora_graph_change_state import persist_state, prepare_state, validate_review
from backend.canvas.test_graph_card import node
from backend.canvas.test_project_architecture import domain, page
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State, default_done, default_state
from backend.editor.node.test_removals import branch, edge_report, state_block, state_node


@pytest.fixture
def canvas(tmp_path):
    service = CanvasService(tmp_path / "data")
    yield service
    service.close()


def graph(*nodes, edges=()):
    return {"nodes": list(nodes), "edges": list(edges)}


def install(canvas, state, revision=1):
    db = canvas.db_for("draft")
    db.execute("INSERT OR REPLACE INTO desktop_v3_state VALUES('draft','draft',?,?,?)",
               (revision, encode(state), f"timestamp-{revision}"))
    db.commit()


def review(canvas, before, after, removed=(), edges=(), rewired=(), working=None):
    return prepare_state(canvas, "draft", "draft", before, working or before, after, after,
                         list(removed), list(edges), list(rewired))


def test_cleanup_archives_exact_effects_and_preserves_tickets_and_history(canvas):
    state = default_state()
    state["nodes"] = {"remove": state_node(), "keep": state_node()}
    state["edges"] = {"edge": edge_report()}
    state["rules"] = [{"id": "rule", "kind": "must", "scope": "node", "target": "remove", "text": "Keep history"}]
    state["decisions"] = [{"id": "decision", "text": "Decided", "pinned": False, "path": "", "nodeId": "remove",
                           "createdAt": "2026-10-21T00:00:00Z", "by": "human"}]
    state["autonomy"] = {"remove": {"until": "2026-11-01T00:00:00Z", "grantedAt": "2026-10-21T00:00:00Z", "note": "Granted"}}
    state["tickets"] = [{"id": "ticket", "title": "Preserve task", "priority": "normal", "status": "open",
                         "nodeId": "remove", "sessionId": "", "createdBy": "human"}]
    install(canvas, state)
    before = graph(node("remove"), node("keep"), edges=[{"id": "edge", "source": "remove", "target": "keep"}])
    after = graph(node("keep"))
    prepared = review(canvas, before, after, ["remove"], ["edge"])
    assert prepared["before"] == state
    assert prepared["after"]["tickets"][0] == {**state["tickets"][0], "nodeId": ""}
    assert prepared["effects"]["removedNodes"] == {"remove": state["nodes"]["remove"]}
    assert prepared["effects"]["removedEdges"] == state["edges"]
    assert prepared["effects"]["removedRules"] == state["rules"]
    assert prepared["effects"]["removedDecisions"] == state["decisions"]
    assert prepared["effects"]["removedAutonomy"] == state["autonomy"]
    db = canvas.db_for("draft")
    db.execute("INSERT INTO opora_execution_epochs VALUES('draft','draft','remove',8)")
    db.execute("INSERT INTO node_spec_revisions VALUES('draft','draft','remove',1,'{}','now')")
    db.execute("INSERT INTO node_text_revisions VALUES('draft','draft','remove',1,'historical text','now')")
    db.execute("INSERT INTO agent_workspace_revisions VALUES('draft','draft','remove',1,'{}','human','now')")
    db.commit()
    history = {table: list(db.execute(f"SELECT * FROM {table}")) for table in
               ("opora_execution_epochs", "node_spec_revisions", "agent_workspace_revisions", "node_text_revisions")}
    db.execute("BEGIN IMMEDIATE")
    assert persist_state(canvas, db, "draft", "draft", prepared, after, actor="human") == 2
    assert db.in_transaction
    for table, rows in history.items():
        assert list(db.execute(f"SELECT * FROM {table}")) == rows
    db.rollback()
    assert DesktopV3State(canvas).current("draft", "draft")["state"] == state


def test_rewire_clears_prior_report_without_changing_node_state(canvas):
    state = default_state()
    state["edges"] = {"edge": edge_report()}
    install(canvas, state)
    nodes = [node("a"), node("b"), node("c")]
    before = graph(*nodes, edges=[{"id": "edge", "source": "a", "target": "b"}])
    after = graph(*nodes, edges=[{"id": "edge", "source": "a", "target": "c"}])
    prepared = review(canvas, before, after, rewired=["edge"])
    assert prepared["after"]["edges"] == {}
    assert prepared["effects"]["clearedEdgeReports"] == state["edges"]


def test_removal_requires_explicit_descendants_and_incident_edges(canvas):
    before = graph(node("parent", kind="sector"), node("child", parent_id="parent"), node("other"),
                   edges=[{"id": "edge", "source": "child", "target": "other"}])
    with pytest.raises(ValueError, match="nodes=child"):
        review(canvas, before, graph(node("other")), ["parent"])
    with pytest.raises(ValueError, match="edges=edge"):
        review(canvas, before, graph(node("other")), ["parent", "child"])


def test_surviving_branch_reference_rejects_without_mutating_state(canvas):
    state = default_state()
    state["nodes"] = {"keep": state_node(blocks=[state_block(on_met=branch("node", "remove"))])}
    install(canvas, state)
    with pytest.raises(ValueError, match="Surviving block reference"):
        review(canvas, graph(node("remove"), node("keep")), graph(node("keep")), ["remove"])
    assert DesktopV3State(canvas).current("draft", "draft")["state"] == state


@pytest.mark.parametrize("operation", ["rename", "delete", "purpose"])
def test_confirmed_cards_need_human_reopening_for_semantic_change(canvas, operation):
    state = default_state()
    state["nodes"] = {"closed": state_node(done={**default_done(), "confirmed": True,
                                                 "at": "2026-10-21T00:00:00Z"})}
    install(canvas, state)
    before = graph(node("closed"))
    after = graph() if operation == "delete" else graph(node("closed", **{("name" if operation == "rename" else "purpose"): "Changed"}))
    with pytest.raises(ValueError, match="reopen confirmed"):
        review(canvas, before, after, ["closed"] if operation == "delete" else [])


def test_reviewed_state_change_rejected_and_unrelated_rebase_uses_affected_fingerprint(canvas):
    state = default_state()
    state["nodes"] = {"remove": state_node(), "other": state_node()}
    install(canvas, state)
    before, after = graph(node("remove"), node("other")), graph(node("other"))
    original = review(canvas, before, after, ["remove"])
    state["nodes"]["other"]["phase"] = "build"
    install(canvas, state, 2)
    rebased = review(canvas, before, after, ["remove"])
    assert original["affectedDigest"] == rebased["affectedDigest"]
    assert original["beforeDigest"] != rebased["beforeDigest"]
    db = canvas.db_for("draft")
    db.execute("BEGIN IMMEDIATE")
    with pytest.raises(ValueError, match="state changed"):
        persist_state(canvas, db, "draft", "draft", original, after, actor="human")
    db.rollback()


def test_persistence_requires_human_transaction_and_review_integrity(canvas):
    prepared = review(canvas, graph(node("remove")), graph(), ["remove"])
    db = canvas.db_for("draft")
    with pytest.raises(RuntimeError, match="transaction"):
        persist_state(canvas, db, "draft", "draft", prepared, graph(), actor="human")
    db.execute("BEGIN IMMEDIATE")
    with pytest.raises(ValueError, match="human"):
        persist_state(canvas, db, "draft", "draft", prepared, graph(), actor="system")
    corrupt = deepcopy(prepared)
    corrupt["after"]["nodes"] = {"injected": state_node()}
    with pytest.raises(ValueError, match="integrity"):
        validate_review(corrupt)
    db.rollback()


def test_already_absent_working_node_still_archives_current_state(canvas):
    state = default_state()
    state["nodes"] = {"removed": state_node()}
    install(canvas, state)
    prepared = review(canvas, graph(node("removed")), graph(), ["removed"], working=graph())
    assert prepared["effects"]["removedNodes"] == state["nodes"]


def test_area_removal_reports_membership_without_removing_geometric_members(canvas):
    area = node("area", kind="area", x=-20, y=-20, size={"w": 500, "h": 500})
    before, after = graph(area, node("member")), graph(node("member"))
    prepared = review(canvas, before, after, ["area"])
    assert prepared["removedNodeIds"] == ["area"]
    assert {item["nodeId"] for item in prepared["effects"]["areaMembershipChanges"]} == {"member"}
    state = default_state()
    state["nodes"] = {"member": state_node(done={**default_done(), "confirmed": True,
                                                 "at": "2026-10-21T00:00:00Z"})}
    install(canvas, state)
    with pytest.raises(ValueError, match="reopen confirmed"):
        review(canvas, before, after, ["area"])


def test_unreviewed_removal_and_rewire_report_reuse_rejected(canvas):
    before = graph(node("a"), node("b"), node("c"), edges=[{"id": "edge", "source": "a", "target": "b"}])
    with pytest.raises(ValueError, match="unreviewed removal"):
        review(canvas, before, graph(node("b"), node("c")), edges=["edge"])
    after = graph(*before["nodes"], edges=[{"id": "edge", "source": "a", "target": "c"}])
    with pytest.raises(ValueError, match="exact reviewed cleanup"):
        review(canvas, before, after)


def test_explicit_reparent_and_rewire_resolve_removal_dependencies(canvas):
    before = graph(node("parent", kind="sector"), node("child", parent_id="parent"), node("other"),
                   edges=[{"id": "edge", "source": "parent", "target": "other"}])
    after = graph(node("child"), node("other"), edges=[{"id": "edge", "source": "child", "target": "other"}])
    prepared = review(canvas, before, after, ["parent"], rewired=["edge"])
    assert prepared["removedNodeIds"] == ["parent"]
    assert prepared["rewiredEdgeIds"] == ["edge"]
    with pytest.raises(ValueError, match="nodes=child"):
        review(canvas, before, graph(node("child", parent_id="parent"), node("other"), edges=after["edges"]),
               ["parent"], rewired=["edge"])
    with pytest.raises(ValueError, match="edges=edge"):
        review(canvas, before, graph(node("child"), node("other"), edges=before["edges"]), ["parent"])


def test_explicit_architecture_context_adopts_only_exact_current_boundary(canvas):
    accepted = graph(domain(host="old.example.cz"), page(), node("task"))
    working = graph(domain(host="current.example.cz"), page(), node("task"))
    args = (canvas, "draft", "draft", accepted, working, working, working, [], [], [])
    with pytest.raises(ValueError, match="shared architecture"):
        prepare_state(*args)
    prepared = prepare_state(*args, adopt_architecture=True)
    assert prepared["after"] == prepared["before"]
    with pytest.raises(ValueError, match="boundary exactly"):
        prepare_state(canvas, "draft", "draft", accepted, working, working, accepted, [], [], [], adopt_architecture=True)
    other = graph(domain(host="unapproved.example.cz"), page(), node("task"))
    with pytest.raises(ValueError, match="shared architecture"):
        prepare_state(canvas, "draft", "draft", accepted, working, other, working, [], [], [], adopt_architecture=True)


@pytest.mark.parametrize("operation", ["add", "rename", "move-out"])
def test_closed_ancestor_protects_new_and_existing_children(canvas, operation):
    root = node("root", kind="sector")
    child = node("child", parent_id="root")
    before = graph(root) if operation == "add" else graph(root, child)
    after = deepcopy(graph(root, child))
    if operation == "rename":
        after["nodes"][1]["name"] = "Renamed child"
    if operation == "move-out":
        after["nodes"][1]["parentId"] = None
    state = default_state()
    state["nodes"] = {"root": state_node(done={**default_done(), "confirmed": True,
                                               "at": "2026-10-21T00:00:00Z"})}
    install(canvas, state)
    with pytest.raises(ValueError, match="reopen confirmed.*root"):
        review(canvas, before, after)


def test_ancestor_state_is_part_of_rebase_preconditions(canvas):
    root = node("root", kind="sector")
    before, after = graph(root), graph(root, node("child", parent_id="root"))
    initial = review(canvas, before, after)
    assert "root" in initial["checkedNodeIds"]
    state = default_state()
    state["nodes"] = {"root": state_node()}
    install(canvas, state)
    assert review(canvas, before, after)["affectedDigest"] != initial["affectedDigest"]
