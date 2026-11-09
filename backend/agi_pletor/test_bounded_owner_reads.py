"""Owner-global model input stays bounded and unfinished reads cannot release writes."""
import json
from types import SimpleNamespace

import pytest

from backend.agi_pletor import research_context, research_turn
from backend.agi_pletor.research_access import OwnerResearchRead
from backend.agi_pletor.solution_projection import project as project_solutions, size
from backend.api.editor.test_research_routes import card
from backend.canvas.canvas_service import CanvasService
from backend.editor.node.test_removals import node
from backend.editor.research import knowledge, service as research, solution_ranking


def test_real_82_card_native_result_is_bounded_without_mutating_native_payload(tmp_path, monkeypatch):
    canvas = CanvasService(tmp_path / "data")
    try:
        other = canvas.project_hub.empty_project({"name": "Second login", "confirmed": True})["id"]
        for project in ("draft", other):
            canvas.save_graph(project, "draft", {"nodes": [{**node("login"), "purpose": "Login architecture " * 200}], "edges": []},
                              canvas.view(project, "draft")["digest"])
        research.apply(canvas, {"project": "draft", "workspace": "draft", "key": "82-sources",
            "operations": [card(f"source{i}", summary="Stored source " * 100) for i in range(82)]}, "human")
        ref = {"projectId": "draft", "workspaceId": "draft", "id": "source0", "revision": 1}
        knowledge.bind(canvas, other, "draft", "login", ref, 0, False, lambda *_: None, "human")
        monkeypatch.setattr(solution_ranking, "WorkerRunner", lambda: lambda query, texts: [.9] * len(texts))
        scopes = [{"project": project, "workspace": "draft"} for project in ("draft", other)]
        access = OwnerResearchRead(canvas, "human")
        native = knowledge.solutions(canvas, scopes, "login", 2, access.authorize)
        before = json.dumps(native, sort_keys=True)
        assert max(len(item["evidence"]) for item in native["solutions"]) == 82
        projected = project_solutions(native)
        actual = access.payload({"type": "research_read", "resultType": "solution", "query": "login", "scopes": scopes, "resultLimit": 2})
        assert size(native) > 100_000 and size(projected) <= 18_000 and size(actual) <= 18_000
        assert json.dumps(native, sort_keys=True) == before
        assert [item["solutionRef"] for item in projected["solutions"]] == [item["solutionRef"] for item in native["solutions"]]
        assert projected["retrieval"]["used"] == "hybrid"
        assert projected["comparison"]["commonSources"] == [ref]
        assert projected["comparison"]["valuesOmitted"]
        first = next(item for item in projected["solutions"] if item["solutionRef"]["projectId"] == "draft")
        assert first["projection"]["sourcesAvailable"] == 82 and first["projection"]["sourcesReturned"] <= 4
        assert first["projection"]["purposeTruncated"] and first["verification"]["status"] == "unknown"
        exact = access.payload({"type": "research_read", "source": ref})
        assert exact["canonicalRef"] == ref and exact["card"]["summary"] == "Stored source " * 100
    finally:
        canvas.close()


def setup_loop(monkeypatch, payload=None):
    monkeypatch.setattr(research_context, "overview", lambda *_: "")
    access = SimpleNamespace(overview=lambda: "owner grant", payload=lambda action: payload or {"content": "x" * 6870})
    action = {"type": "research_read", "source": {"projectId": "p", "workspaceId": "w", "id": "exact", "revision": 1}}
    return access, action


def test_premature_final_after_6000_of_6885_is_discarded_and_exact_remainder_read(monkeypatch):
    access, action = setup_loop(monkeypatch)
    assert size(access.payload(action)) == 6885
    calls, emitted = [], []
    write = {"type": "heart_message", "text": "premature write"}
    def run(context, *args, **kwargs):
        calls.append(context)
        if len(calls) == 1:
            return "", [action, write]
        if len(calls) == 2:
            kwargs["on_delta"]("Premature stream must not escape")
            return "Premature answer", [write]
        assert '"offset": 6000' in context and '"nextOffset": null' in context
        return "Complete answer", []
    result = research_turn.turn(run, None, "p", "w", "", "?", access=access, on_delta=emitted.append)
    assert result == ("Complete answer", []) and emitted == ["Complete answer"] and len(calls) == 3


@pytest.mark.parametrize("failure", ["error", "skip", "budget"])
def test_owner_continuation_error_gap_or_budget_never_releases_model_writes(monkeypatch, failure):
    access, action = setup_loop(monkeypatch, {"content": "x" * 100_000} if failure == "budget" else None)
    calls = []
    if failure == "budget":
        monkeypatch.setattr(research_turn, "MAX_READS", 2)
    if failure == "error":
        original = access.payload
        def changed(action):
            if action.get("offset"):
                return {"content": "changed snapshot"}
            return original(action)
        access.payload = changed
    def run(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            return "", [action]
        if failure == "skip":
            return "", [{**action, "offset": 6500, "snapshot": "invented"}]
        return "Must not escape", [{"type": "heart_message", "text": "unsafe"}]
    reply, writes = research_turn.turn(run, None, "p", "w", "", "?", access=access)
    assert writes == [] and reply != "Must not escape"
    assert ("limitu" in reply) if failure == "budget" else ("bezpečně" in reply)


def test_escaped_long_facts_remain_bounded_and_proof_status_never_changes():
    ref = {"projectId": "p" * 100, "workspaceId": "w" * 100, "id": "s" * 100, "revision": 1}
    entry = {"solutionRef": {"projectId": "p", "nodeId": "login"}, "title": "\x01" * 500,
        "purpose": "\x01" * 2000, "snapshot": {"workspaceId": "w", "graphDigest": "a" * 64},
        "verification": {"status": "reported_evidence", "verified": True, "independent": False,
                         "receiptId": "receipt", "reason": "Long native detail" * 1000},
        "facts": {"specification": {"acceptedRevision": "a" * 40, "revision": 1,
            "fields": {key: "\x01" * 2000 for key in ("goal", "acceptance", "non_goals")}},
            "inputs": [{"nodeId": "input", "name": "\x01" * 2000}] * 50, "sources": [ref] * 82},
        "evidence": [{}] * 82}
    result = project_solutions({"solutions": [entry, entry], "ranking": "hybrid", "retrieval": {},
        "truncated": False, "comparison": {"commonSources": [ref] * 82, "differences": [{"field": "purpose", "values": ["duplicate"]}]}})
    assert size(result) <= 18_000
    for item in result["solutions"]:
        assert item["verification"]["verified"] is True and item["verification"]["independent"] is False
        assert item["verification"]["receiptId"] == "receipt"
        assert item["projection"]["fieldsTruncated"]
        assert all(source == ref for source in item["facts"]["sources"])
    assert result["comparison"]["commonSourcesAvailable"] == 82


def test_owner_cannot_begin_with_tail_from_previous_turn(monkeypatch):
    access, action = setup_loop(monkeypatch)
    result = research_turn.turn(lambda *args, **kwargs: ("unsafe", [{**action, "offset": 6000, "snapshot": "old"}]),
                                None, "p", "w", "", "?", access=access)
    assert result[1] == [] and "offset 0" in result[0]
