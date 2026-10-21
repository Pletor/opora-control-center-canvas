"""Auto-rebase covers graph changes, graph additions and content proposals with the same verdicts."""
from backend.canvas.opora_auto_rebase import AutoRebase
from backend.canvas.opora_content_changes import OporaContentChanges
from backend.canvas.test_opora_content_changes import accepted, change
from backend.canvas.test_opora_content_changes import propose as propose_content
from backend.canvas.test_opora_execution_context import sparse
from backend.canvas.test_opora_graph_changes import approve, edits, graphs, service
from backend.canvas.test_opora_graph_changes import change as graph_change
from backend.canvas.test_opora_graph_initial import empty_graphs
from backend.canvas.test_opora_graph_proposals import accept as accept_additions
from backend.canvas.test_opora_graph_proposals import proposal as additions

__all__ = ["edits", "empty_graphs", "graphs", "service", "sparse"]


def update(edits, node, **fields):
    return graph_change(edits, {"updateNodes": [{"id": node, "fields": fields}]})


def test_graph_disjoint_fields_rebase_and_accept(edits, service):
    first = update(edits, "a", name="Renamed A")
    other = update(edits, "a", purpose="Purpose A")
    approve(edits, first)
    summary = AutoRebase(service).run("draft", "draft")
    assert [item["proposalId"] for item in summary["rebased"]] == [other["id"]]
    moved = edits.read("draft", "draft", summary["rebased"][0]["resultId"])
    assert moved["supersedes"] == other["id"] and moved["by"]["name"] == "system"
    approve(edits, moved)
    node = next(item for item in service.view("draft", "draft")["graph"]["nodes"] if item["id"] == "a")
    assert node["name"] == "Renamed A" and node["purpose"] == "Purpose A"


def test_graph_same_field_conflict_and_redundant(edits, service):
    first = update(edits, "a", name="Ours")
    twin = update(edits, "a", name="Ours", x=first["changes"]["nodes"][0]["acceptedBefore"].get("x", 0))
    rival = update(edits, "a", name="Theirs")
    approve(edits, first)
    rebase = AutoRebase(service)
    summary = rebase.run("draft", "draft")
    assert [item["proposalId"] for item in summary["conflicts"]] == [rival["id"]]
    assert [item["proposalId"] for item in summary["redundant"]] == [twin["id"]]
    item = rebase.conflicts("draft", "draft", "open")["items"][0]["items"][0]
    assert item["key"] == "graph:node:a:name" and item["ours"] == "Theirs" and item["theirs"] == "Ours"


def test_graph_additions_rebase_after_sibling(graphs, service):
    accept_additions(graphs, additions(graphs, "Base"))
    left, right = additions(graphs, "Left"), additions(graphs, "Right")
    accept_additions(graphs, left)
    summary = AutoRebase(service).run("draft", "draft")
    assert [item["proposalId"] for item in summary["rebased"]] == [right["id"]]
    moved = graphs.read("draft", "draft", summary["rebased"][0]["resultId"])
    assert moved["refs"] == right["refs"] and moved["supersedes"] == right["id"]


def test_content_disjoint_redundant_and_conflict(sparse):
    _, authority, refs = sparse
    canvas = authority.canvas
    left = propose_content(sparse, [change("text", refs["a"], "text", "A")])
    disjoint = propose_content(sparse, [change("text", refs["b"], "text", "B")])
    twin = propose_content(sparse, [change("text", refs["a"], "text", "A")], subject="Twin")
    rival = propose_content(sparse, [change("text", refs["a"], "text", "Other")], subject="Rival")
    accepted(sparse, left)
    rebase = AutoRebase(canvas)
    summary = rebase.run("draft", "draft")
    assert [item["proposalId"] for item in summary["rebased"]] == [disjoint["id"]]
    assert [item["proposalId"] for item in summary["redundant"]] == [twin["id"]]
    assert [item["proposalId"] for item in summary["conflicts"]] == [rival["id"]]
    conflict = rebase.conflicts("draft", "draft", "open")["items"][0]["items"][0]
    assert (conflict["ours"], conflict["theirs"]) == ("Other", "A")
    moved = OporaContentChanges(canvas).read("draft", "draft", summary["rebased"][0]["resultId"])["proposal"]
    assert moved["supersedes"] == disjoint["id"] and not moved["requiresBaseContentAdoption"]
    accepted(sparse, moved)
    assert canvas.texts.read(("draft", "draft", refs["b"]))["text"] == "B"
    assert rebase.run("draft", "draft")["rebased"] == []
