"""Bulk solution materialization reuses native snapshots, never cross-request authority."""
from collections import Counter
import pytest

from backend.api.editor.test_research_routes import card
from backend.canvas.test_opora_changesets import baseline, service
from backend.editor.node.test_removals import node
from backend.editor.research import knowledge, service as research, solution_candidates
from database.repositories.opora_changesets import ChangesetRepository

__all__ = ["service"]
SCOPE = {"project": "draft", "workspace": "draft"}


def prepare(canvas):
    view = canvas.view("draft", "draft")
    graph = {"nodes": [node(f"login{i}") for i in range(24)], "edges": []}
    canvas.save_graph("draft", "draft", graph, view["digest"], allow_removal=True)
    baseline(canvas)
    research.apply(canvas, {**SCOPE, "key": "research", "operations": [card("source")]}, "human")


def collect(canvas, authorize=lambda *_: None):
    return solution_candidates.collect(canvas, [SCOPE], "login", authorize, knowledge.context)[0]


def instrument(canvas, monkeypatch):
    reads, views = Counter(), Counter()
    original_read, original_view = ChangesetRepository.read, canvas._view

    def read(repo, identifier, **kwargs):
        reads[(repo.scope, identifier)] += 1
        return original_read(repo, identifier, **kwargs)

    def view(project, workspace):
        views[(project, workspace)] += 1
        return original_view(project, workspace)

    monkeypatch.setattr(ChangesetRepository, "read", read)
    monkeypatch.setattr(canvas, "_view", view)
    return reads, views


def test_bulk_materialization_validates_head_once_and_views_once_per_read(service, monkeypatch):
    prepare(service)
    reads, views = instrument(service, monkeypatch)
    first = collect(service)
    assert len(first) == 24
    assert sum(reads.values()) == 1
    assert views == {("draft", "draft"): 2}  # Candidate selection + materialization snapshot.
    assert all(item["evidence"][0]["card"]["title"] == "Login" for item in first)

    research.apply(service, {**SCOPE, "key": "new-revision", "operations": [card("source", expectedRevision=1, title="Updated")]}, "human")
    reads.clear(); views.clear()
    second = collect(service)
    assert sum(reads.values()) == 1 and views == {("draft", "draft"): 2}
    assert all(item["evidence"][0]["card"]["title"] == "Updated" for item in second)


def test_shared_origin_snapshot_reused_but_every_binding_authorizes(service, monkeypatch):
    prepare(service)
    origin = service.project_hub.empty_project({"name": "Source", "confirmed": True})["id"]
    research.apply(service, {"project": origin, "workspace": "draft", "key": "origin", "operations": [card("canonical")]}, "human")
    ref = {"projectId": origin, "workspaceId": "draft", "id": "canonical", "revision": 1}
    for index in range(24):
        knowledge.bind(service, "draft", "draft", f"login{index}", ref, 0, False, lambda *_: None, "human")
    _, views = instrument(service, monkeypatch)
    authorizations = Counter()

    def authorize(project, workspace, write):
        authorizations[(project, workspace)] += 1

    result = collect(service, authorize)
    assert views[(origin, "draft")] == 1
    assert authorizations[(origin, "draft")] >= 24
    assert all(any(record["canonicalRef"] == ref for record in item["evidence"]) for item in result)
    assert not service._scopes()  # Reader lifetime ends before semantic worker execution.


def test_writer_owned_materialization_uses_only_request_local_steady_cache(service, monkeypatch):
    prepare(service)
    reads, views = instrument(service, monkeypatch)
    with service.lock_for("draft"):
        assert len(collect(service)) == 24
    assert sum(reads.values()) == 1 and views == {("draft", "draft"): 2}
    assert not getattr(service._local, "steady", {})


def test_accepted_record_tampering_between_searches_is_not_cached(service):
    prepare(service)
    assert len(collect(service)) == 24
    db = service.db_for("draft")
    with db:
        db.execute("UPDATE opora_spec_revisions SET content=replace(content, 'Initial specifications', 'Changed specifications')")
    with pytest.raises(ValueError, match="Otisk"):
        collect(service)


def test_solution_validation_does_not_execute_discarded_research_search(service, monkeypatch):
    prepare(service)
    def unused(*args, **kwargs):
        raise AssertionError("Solution validation must not run another research search")
    monkeypatch.setattr(knowledge, "search", unused)
    result = knowledge.solutions(service, [SCOPE], "login", 10, lambda *_: None, ranking="lexical")
    assert result["solutions"] and result["ranking"] == "lexical-all-terms"
