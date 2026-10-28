"""Kontrola mapy přes worktree (docs/navrhy/2026-10-28-kontrola-mapy-a-worktree.md §3)."""
from types import SimpleNamespace

import pytest

from backend.project.architecture import map_check_worktrees as overlay
from backend.project.architecture.map_check import finding_key


def node(identifier, parent=None, **extra):
    return {"id": identifier, "parentId": parent, "kind": "node", "name": identifier, **extra}


def graph(goal=None, edges=()):
    """Aplikace s cestou nav → /a, stránka /a se dvěma komponentami; bez `goal` je díra `page.no-goal`."""
    app = node("app", site={"kind": "application", "environments": [],
                            "journeys": [{"id": "j", "name": "Kurz", "steps": [{"id": "k0", "page": "nav"},
                                                                               {"id": "k1", "page": "a"}]}]})
    page = node("a", "app", site={"kind": "page", "path": "/a", **({"goal": goal} if goal else {})})
    return {"nodes": [app, page, node("c", "a"), node("d", "a")], "edges": list(edges)}


UNSET = {"id": "e1", "source": "c", "target": "d"}


def fake(views, source_kind="git", workspaces=None, broken=()):
    calls = []

    def view(project, wid):
        calls.append(wid)
        if wid in broken:
            raise ValueError("Git operace selhala.")
        data = views[wid]
        return {"graph": data, "digest": f"{wid}:{len(data['edges'])}:{bool(data['nodes'][1]['site'].get('goal'))}"}

    rows = workspaces if workspaces is not None else [
        {"id": wid, "branch": f"work/{wid}", "actor": f"agent-{wid}", "node_id": "app"} for wid in views if wid != "main"]
    service = SimpleNamespace(project_hub=SimpleNamespace(settings=lambda project: {"project": {"sourceKind": source_kind}}),
                              view=view, workspaces=lambda project: rows)
    return service, calls


@pytest.fixture(autouse=True)
def no_runs(monkeypatch):
    monkeypatch.setattr(overlay, "latest_journey_runs", lambda service, project: {})
    overlay._cache.clear()


def test_worktree_closes_main_holes_and_opens_new_ones():
    service, _ = fake({"main": graph(), "w1": graph(goal="Cíl", edges=[UNSET]), "w2": graph()})
    result = overlay.worktree_overlay(service, "p")
    rules = [f["rule"] for f in result["main"]]
    assert rules == ["journey.unverified", "page.no-goal"]
    no_goal = next(f for f in result["main"] if f["rule"] == "page.no-goal")
    assert finding_key(no_goal) == "page.no-goal|a|||a|Stránka nemá cíl (goal)."
    assert result["worktrees"] == [
        {"workspaceId": "w1", "branch": "work/w1", "actor": "agent-w1", "domainId": "app",
         "closed": [finding_key(no_goal)],
         "opened": [{"rule": "edge.carries-unset", "edgeId": "e1", "message": "Vazba neříká, co nese (carries).",
                     "solverId": "c"}]},
        {"workspaceId": "w2", "branch": "work/w2", "actor": "agent-w2", "domainId": "app", "closed": [], "opened": []}]


def test_unverified_journey_is_never_closed_by_a_worktree():
    service, _ = fake({"main": graph(goal="Cíl"), "w1": graph(goal="Cíl")})
    result = overlay.worktree_overlay(service, "p")
    assert [f["rule"] for f in result["main"]] == ["journey.unverified"]
    assert result["worktrees"][0]["closed"] == [] and result["worktrees"][0]["opened"] == []


def test_project_without_git_has_no_worktrees():
    service, calls = fake({"draft": graph()}, source_kind="folder", workspaces=[{"id": "w1"}])
    result = overlay.worktree_overlay(service, "p")
    assert result["worktrees"] == [] and calls == ["draft"]
    assert [f["rule"] for f in result["main"]] == ["journey.unverified", "page.no-goal"]


def test_main_row_and_unreadable_worktree_are_skipped():
    views = {"main": graph(), "w1": graph(goal="Cíl")}
    rows = [{"id": "main"}, {"id": "zmizel"}, {"id": "w1", "branch": "work/w1", "actor": None, "node_id": None}]
    service, _ = fake(views, workspaces=rows, broken={"zmizel"})
    assert [tree["workspaceId"] for tree in overlay.worktree_overlay(service, "p")["worktrees"]] == ["w1"]


def test_unchanged_worktree_is_checked_once(monkeypatch):
    service, _ = fake({"main": graph(), "w1": graph(goal="Cíl")})
    checked = []
    original = overlay.check_map
    monkeypatch.setattr(overlay, "check_map", lambda data, runs=None, locate=False: checked.append(runs is None)
                        or original(data, runs, locate=locate))
    first = overlay.worktree_overlay(service, "p")
    assert overlay.worktree_overlay(service, "p") == first
    assert checked == [False, True, False]  # main dvakrát (doklady se mění bez grafu), worktree jednou


def test_opened_holes_stop_at_fifty():
    many = [{"id": f"e{i:02}", "source": "c", "target": "d"} for i in range(60)]
    service, _ = fake({"main": graph(), "w1": graph(edges=many)})
    opened = overlay.worktree_overlay(service, "p")["worktrees"][0]["opened"]
    assert len(opened) == overlay.OPENED_LIMIT == 50 and opened[0]["edgeId"] == "e00"
