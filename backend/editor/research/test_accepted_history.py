"""Native immutable history validates once per steady read, never across later writes."""
from collections import Counter

import pytest

from backend.brain_opora.determinism.test_milestone_evidence import prepare_integration
from backend.brain_opora.determinism.test_milestones import service
from backend.editor.research.execution_evidence import collect
from database.repositories.opora_graph_changes import GraphChanges

__all__ = ["service"]


def test_all_cards_share_native_history_validation_only_for_one_locked_read(service, monkeypatch):
    _, _, _, proof = prepare_integration(service)
    db = service.db_for("draft")
    calls = Counter()
    original = GraphChanges.read
    def counted(self, identifier, *, manifest=False):
        calls[(identifier, manifest)] += 1
        return original(self, identifier, manifest=manifest)
    monkeypatch.setattr(GraphChanges, "read", counted)
    before = db.total_changes
    with service.graph_lock_for("draft"), service.lock_for("draft"), service.steady_reads("draft"):
        results = [collect(db,"draft","draft",proof["acceptedRevision"],[node],canvas=service)
                   for node in ("n1","n2","n3")]
    assert calls and set(calls.values()) == {1}
    first = dict(calls)
    assert all(item["canonicalScopes"]["scopeNodeIds"] == ["",node] for item,node in zip(results,("n1","n2","n3"),strict=True))
    assert db.total_changes == before
    with service.graph_lock_for("draft"), service.lock_for("draft"), service.steady_reads("draft"):
        collect(db,"draft","draft",proof["acceptedRevision"],["n1"],canvas=service)
    assert calls == {key:count*2 for key,count in first.items()}
    assert getattr(service._local,"steady",{}) == {}


def test_new_read_rechecks_native_integrity_after_database_mutation(service):
    _, _, _, proof = prepare_integration(service)
    db = service.db_for("draft")
    with service.graph_lock_for("draft"), service.lock_for("draft"), service.steady_reads("draft"):
        collect(db,"draft","draft",proof["acceptedRevision"],["n1"],canvas=service)
    with db:
        db.execute("UPDATE opora_graph_proposals SET content='{}' WHERE project_id='draft' AND workspace_id='draft'")
    with service.graph_lock_for("draft"), service.lock_for("draft"), service.steady_reads("draft"):
        with pytest.raises(ValueError):
            collect(db,"draft","draft",proof["acceptedRevision"],["n1"],canvas=service)


def test_db_only_callers_keep_fresh_reads_without_a_canvas_cache(service, monkeypatch):
    _, _, _, proof = prepare_integration(service)
    calls = Counter()
    original = GraphChanges.read
    def counted(self, identifier, *, manifest=False):
        calls[(identifier,manifest)] += 1
        return original(self,identifier,manifest=manifest)
    monkeypatch.setattr(GraphChanges,"read",counted)
    for _ in range(2):
        collect(service.db_for("draft"),"draft","draft",proof["acceptedRevision"],["n1"])
    assert calls and set(calls.values()) == {2}
