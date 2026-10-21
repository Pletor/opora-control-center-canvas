"""History and blame are derived from accepted changesets and stay correct across auto-rebases."""
from backend.canvas.opora_auto_rebase import AutoRebase
from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.opora_derived_history import DerivedHistory
from backend.canvas.test_opora_auto_rebase import propose
from backend.canvas.test_opora_changesets import AGENT, HUMAN, accept, baseline, service
from backend.canvas.test_opora_graph_changes import approve, edits, graphs
from backend.canvas.test_opora_graph_changes import change as graph_change

__all__ = ["edits", "graphs", "service"]


def test_history_and_blame_follow_rebased_changesets(service):
    root = baseline(service)
    goal = propose(service, "a", goal="G1")
    acceptance = propose(service, "a", acceptance="X")
    first = accept(service, goal, root["id"])
    moved = AutoRebase(service).run("draft", "draft")["rebased"][0]["resultId"]
    second = accept(service, OporaChangesets(service).read("draft", "draft", moved), first["id"])
    derived = DerivedHistory(service)
    history = derived.history("draft", "draft", "a")
    assert [item["revisionId"] for item in history["items"]] == [root["id"], first["id"], second["id"]]
    assert history["items"][1]["changedKeys"] == ["spec:goal"]
    assert history["items"][2]["changedKeys"] == ["spec:acceptance"]
    last = history["items"][2]
    assert last["author"] == {"kind": "orchestrator", "name": "system"} and last["originalAuthor"] == AGENT
    assert last["rebasedFrom"] == acceptance["id"] and last["acceptedBy"] == HUMAN
    assert last["proposalKind"] == "spec" and last["acceptedAt"] == second["createdAt"]
    blame = {item["key"]: item["revisionId"] for item in derived.blame("draft", "draft", "a")["items"]}
    assert blame == {"spec:goal": first["id"], "spec:acceptance": second["id"], "spec:non_goals": root["id"]}
    assert [item["revisionId"] for item in derived.history("draft", "draft", "b")["items"]] == [root["id"]]
    assert derived.rebuild("draft", "draft") == {"acceptedHead": second["id"], "revisions": 3}
    assert derived.history("draft", "draft", "a") == history


def test_blame_tracks_graph_fields_and_cache_is_keyed_by_revision(edits, service):
    item = graph_change(edits, {"updateNodes": [{"id": "a", "fields": {"name": "Graph name"}}]})
    revision = approve(edits, item)
    derived = DerivedHistory(service)
    blame = {entry["key"]: entry for entry in derived.blame("draft", "draft", "a")["items"]}
    assert blame["graph:node:name"]["revisionId"] == revision["id"]
    assert blame["graph:node:name"]["proposalKind"] == "graph"
    assert blame["spec:goal"]["revisionId"] != revision["id"]
    db = service.db_for("draft")
    count = db.execute("SELECT COUNT(*) FROM opora_derived_revisions").fetchone()[0]
    derived.history("draft", "draft", "a")
    assert db.execute("SELECT COUNT(*) FROM opora_derived_revisions").fetchone()[0] == count


def test_empty_history_without_accepted_head(service):
    assert DerivedHistory(service).history("draft", "draft", "a") == {"cardId": "a", "acceptedHead": None, "items": []}
