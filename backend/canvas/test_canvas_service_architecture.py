"""Architektura nad worktree (docs/domeny-a-worktree.md §4): složený pohled, pravidla zápisu, odebrání, undo."""

import json
from pathlib import Path

import pytest

from backend.canvas.canvas_plan import apply_plan
from backend.canvas.test_canvas_service import git, managed_fixture
from backend.canvas.test_graph_card import node
from backend.canvas.test_project_architecture import domain, page


def add(s, pid, wid, *items, edges=()):
    current = s.view(pid, wid)
    graph = {"nodes": [*current["graph"]["nodes"], *items], "edges": [*current["graph"]["edges"], *edges]}
    return s.save_graph(pid, wid, graph, current["digest"], actor="human")


def node_ids(view):
    return [n["id"] for n in view["graph"]["nodes"]]


@pytest.fixture
def project(tmp_path):
    s, p = managed_fixture(tmp_path)
    a = s.create_workspace(p["id"], "project", "Agent A")
    b = s.create_workspace(p["id"], "project", "Agent B")
    yield s, p["id"], a["id"], b["id"]
    s.close()


def test_composed_view_and_architecture_from_main(project):
    s, pid, a, b = project
    main = s.view(pid, "main")
    assert main["readOnly"] is True and main["architectureEditable"] is True and main["architectureRevision"] == 0
    saved = add(s, pid, "main", domain(), page())
    assert saved["architectureRevision"] == 1
    add(s, pid, a, node("card", parent_id="page"))
    view_a, view_b = s.view(pid, a), s.view(pid, b)
    assert node_ids(view_a) == ["app", "page", "card"]
    assert node_ids(view_b) == ["app", "page"]
    assert view_a["architectureEditable"] is True and view_b["architectureRevision"] == 1
    # Do souboru prostoru jde jen obsah; architektura leží v project.sqlite.
    stored = json.loads(s.graph_file(pid, a).read_text(encoding="utf-8"))
    assert [n["id"] for n in stored["nodes"]] == ["card"]
    with pytest.raises(ValueError, match="pouze pro čtení"):
        add(s, pid, "main", node("loose"))


def test_site_node_saved_in_worktree_moves_to_architecture(project):
    s, pid, a, b = project
    add(s, pid, a, domain(), page(), node("card", parent_id="page"))
    assert [n["id"] for n in s.architecture.read(pid)["graph"]["nodes"]] == ["app", "page"]
    assert node_ids(s.view(pid, b)) == ["app", "page"]
    assert s.architecture.history(pid)[0]["workspace"] == a


def test_concurrent_architecture_change_is_a_digest_conflict(project):
    s, pid, a, _b = project
    stale = s.view(pid, a)
    add(s, pid, "main", domain())
    graph = {"nodes": [node("card")], "edges": []}
    with pytest.raises(ValueError, match="změnilo"):
        s.save_graph(pid, a, graph, stale["digest"])


def test_host_is_unique_across_worktrees(project):
    s, pid, a, b = project
    add(s, pid, a, domain())
    with pytest.raises(ValueError, match="host"):
        add(s, pid, b, domain("other"))


def test_removal_is_blocked_by_reference_from_another_worktree(project):
    s, pid, a, b = project
    add(s, pid, "main", domain(), page())
    add(s, pid, a, node("card", parent_id="page"))
    preview = s.removals.preview(pid, b, "node", "page")
    assert [hit["workspace"] for hit in preview["blockedBy"]] == [a]
    payload = {"project": pid, "workspace": b, "kind": "node", "target": "page",
               "digest": preview["digest"], "confirmed": True}
    with pytest.raises(ValueError, match="odkazují"):
        s.removals.remove(payload, actor="human")
    # Doména, ke které patří worktree, se taky neodebere.
    with s.registry_lock:
        s.db.execute("UPDATE workspaces SET node_id='app' WHERE id=?", (b,))
        s.db.commit()
    reasons = {hit["reason"] for hit in s.removals.preview(pid, "main", "node", "app")["blockedBy"]}
    assert reasons == {"obsah", "worktree domény"}


def test_architecture_removal_on_main_hides_legacy_head_copy(project, tmp_path):
    s, pid, _a, _b = project
    repo = Path(s.row("projects", pid)["repo"])
    git(repo, "config", "user.name", "Fixture")
    git(repo, "config", "user.email", "fixture@example.invalid")
    (repo / "opora-canvas.json").write_text(json.dumps({"nodes": [domain()], "edges": []}), encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "legacy graph")
    assert node_ids(s.view(pid, "main")) == ["app"]
    add(s, pid, "main", page())  # stránka na mainu převezme doménu z HEAD do architektury
    assert [n["id"] for n in s.architecture.read(pid)["graph"]["nodes"]] == ["app", "page"]
    preview = s.removals.preview(pid, "main", "node", "app")
    assert preview["blockedBy"] == []
    s.removals.remove({"project": pid, "workspace": "main", "kind": "node", "target": "app",
                       "digest": preview["digest"], "confirmed": True}, actor="human")
    # HEAD:opora-canvas.json doménu pořád nese, ale smazaná architektura se nevrací.
    assert node_ids(s.view(pid, "main")) == []
    assert s.architecture.read(pid)["removed"]["nodes"] == ["app", "page"]


def test_undo_restores_content_only_and_refuses_orphans(project):
    s, pid, a, _b = project
    add(s, pid, a, domain(), page())
    before = s.view(pid, a)
    add(s, pid, a, node("card", parent_id="page"))
    moved = s.view(pid, a)
    edited = {"nodes": [{**n, "x": 50} if n["id"] == "app" else n for n in moved["graph"]["nodes"]],
              "edges": moved["graph"]["edges"]}
    s.save_graph(pid, a, edited, moved["digest"])
    undone = s.save_graph(pid, a, before["graph"], s.view(pid, a)["digest"], undo=True)
    assert node_ids(undone) == ["app", "page"]
    assert undone["graph"]["nodes"][0]["x"] == 50  # architektura zůstala současná
    # Snímek s kartou pod smazanou stránkou se nevrátí potichu bez rodiče.
    with_card = {"nodes": [*undone["graph"]["nodes"], node("card", parent_id="page")], "edges": []}
    s.architecture.save({"project": pid, "workspace": a, "expectedRevision": s.architecture.read(pid)["revision"],
                         "graph": {"nodes": [undone["graph"]["nodes"][0]], "edges": []}})
    with pytest.raises(ValueError, match="už v architektuře není"):
        s.save_graph(pid, a, with_card, s.view(pid, a)["digest"], undo=True)


def test_architecture_specs_and_texts_live_under_reserved_workspace(project):
    s, pid, a, _b = project
    add(s, pid, "main", domain(), page())
    fields = {"goal": "Přehled účtu", "non_goals": "", "acceptance": ""}
    saved = s.node_spec(pid, "main", "page", {"project": pid, "workspace": "main", "node": "page",
                                              "expected_revision": 0, "fields": fields})
    assert saved["revision"] == 1 and saved["readOnly"] is False
    assert s.node_spec(pid, a, "page")["fields"] == fields
    s.texts.access(pid, a, "page", {"project": pid, "workspace": a, "node": "page",
                                    "expected_revision": 0, "text": "Popis stránky"})
    assert s.texts.access(pid, "main", "page")["text"] == "Popis stránky"
    assert s.specs.read((pid, "architecture", "page"))["revision"] == 1


def test_plan_on_main_may_only_touch_architecture(project):
    s, pid, _a, _b = project
    digest = s.view(pid, "main")["digest"]
    plan = {"nodes": [{"ref": "app", "kind": "sector", "name": "Aplikace", "purpose": "Web projektu",
                       "site": {"kind": "application", "environments": [{"name": "Produkce", "host": "app.example.cz"}]}},
                      {"ref": "page", "kind": "node", "parent": "app", "name": "Přehled", "purpose": "",
                       "site": {"kind": "page", "path": "/"}, "spec": {"goal": "Ukázat stav"}}]}
    result = apply_plan(s, {"project": pid, "workspace": "main", "digest": digest, "plan": plan}, actor="human")
    page_id = result["refs"]["page"]
    assert s.node_spec(pid, "main", page_id)["fields"]["goal"] == "Ukázat stav"
    card = {"nodes": [{"ref": "c", "kind": "node", "name": "Karta", "purpose": ""}]}
    with pytest.raises(ValueError, match="pouze pro čtení"):
        apply_plan(s, {"project": pid, "workspace": "main", "digest": s.view(pid, "main")["digest"], "plan": card},
                   actor="human")


def test_restore_is_blocked_when_a_worktree_uses_the_dropped_page(project):
    s, pid, a, _b = project
    add(s, pid, "main", domain())
    add(s, pid, "main", page())
    add(s, pid, a, node("card", parent_id="page"))
    current = s.architecture.read(pid)
    with pytest.raises(ValueError, match="odkazují"):
        s.architecture.restore({"project": pid, "revision": 1, "digest": current["digest"]})
