"""LLM čte skutečný úplný detail po částech, bez možnosti změnit rozsah dotazem."""
import json
from types import SimpleNamespace

from backend.agi_pletor import research_context as context
from backend.brain_opora.determinism.gate_payloads import GateError


def card(id="rc_one"):
    return {"id": id, "title": "Přihlášení", "topicPath": ["Přihlášení", "Logika"],
            "verification": {"status": "verified"}, "refs": {"questionIds": ["pq_1"]}}


def test_overview_is_headers_only_and_reads_all_detail_chunks(monkeypatch):
    full = {"card": {**card(), "content": "dlouhý rozbor " * 1000 + "KONEC", "sources": [
        {"ref": f"https://example.org/{n}", "quote": f"doklad {n}"} for n in range(9)]}, "edges": [], "history": []}
    monkeypatch.setattr(context.research, "listing", lambda *a, **kw: {"cards": [card()], "edges": []})
    calls = []

    def detail(service, project, workspace, id, revision=None):
        calls.append((project, workspace, id, revision))
        return full

    monkeypatch.setattr(context.research, "detail", detail)
    overview = context.overview(None, "p", "draft")
    assert "rc_one" in overview and "dlouhý rozbor" not in overview
    chunks, offset, snapshot = [], 0, None
    while offset is not None:
        result = context.read(None, "p", "draft", {"type": "research_read", "cardId": "rc_one", "offset": offset, "snapshot": snapshot})
        chunks.append(result["data"])
        offset = result["nextOffset"]
        snapshot = result["snapshot"]
    assert json.loads("".join(chunks)) == full
    assert len(chunks) > 1 and all(c[:2] == ("p", "draft") for c in calls)


def test_search_retains_semantic_edges_and_scope(monkeypatch):
    edge = {"fromId": "rc_one", "toId": "rc_two", "relation": "continues_to", "reason": "UX hotovo, logika chybí"}
    monkeypatch.setattr(context.research, "listing", lambda *a, **kw: {"cards": [card()], "edges": [edge]})
    result = context.read(None, "p", "draft", {"type": "research_read", "query": "pq_1"})
    assert json.loads(result["data"])["edges"] == [edge]
    assert "error" in context.read(None, "p", "draft", {"type": "research_read", "workspace": "foreign"})
    assert "error" in context.read(None, "p", "draft", {"type": "research_read", "limit": 100000})
    assert "error" in context.read(None, "p", "draft", {"type": "research_read", "offset": True})


def test_not_found_is_data_not_fabricated_fact(monkeypatch):
    def missing(*args, **kwargs):
        raise GateError(404, "research_not_found", "V tomto prostoru není.", "Zkontroluj ID.")
    monkeypatch.setattr(context.research, "detail", missing)
    assert context.read(None, "p", "draft", {"type": "research_read", "cardId": "rc_foreign"})["error"]


def test_main_resolves_only_server_active_workspace(tmp_path, monkeypatch):
    service = SimpleNamespace(folder=lambda p: SimpleNamespace(path=tmp_path / p))
    brain = tmp_path / "p" / "brain"
    brain.mkdir(parents=True)
    (brain / "active_workspace.json").write_text('{"workspace":"feature"}', encoding="utf-8")
    assert context.workspace_for(service, "p", "main") == "feature"
    assert context.workspace_for(service, "p", "other") == "other"


def test_edge_revision_and_concurrent_change_are_explicit(monkeypatch):
    payload = {"edge": {"id": "re_one", "revision": 2, "reason": "A" * 8000}, "history": []}
    monkeypatch.setattr(context.research, "edge_detail", lambda *a, **kw: payload)
    action = {"type": "research_read", "edgeId": "re_one", "revision": 2}
    first = context.read(None, "p", "draft", action)
    assert first["nextOffset"] is not None
    continuation = {**action, "offset": first["nextOffset"], "snapshot": first["snapshot"]}
    assert "data" in context.read(None, "p", "draft", continuation)
    assert "error" in context.read(None, "p", "other", continuation)
    payload["history"].append({"revision": 3})
    assert "změnily" in context.read(None, "p", "draft", continuation)["error"]
    assert "error" in context.read(None, "p", "draft", {**action, "offset": 1})
