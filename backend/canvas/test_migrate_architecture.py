"""Migrace architektury z grafů prostorů (docs/domeny-a-worktree.md §5): zdroje, konflikty, fáze, idempotence."""

import json
from pathlib import Path

import pytest

import backend.canvas.migrate_architecture as module
from backend.canvas.canvas_service import CanvasService
from backend.canvas.graph import encode
from backend.canvas.migrate_architecture import migrate
from backend.canvas.test_canvas_service import git, managed_fixture
from backend.canvas.test_graph_card import node
from backend.canvas.test_project_architecture import domain, page
from backend.canvas.workspace_graph import write_workspace_graph

ARCH_EDGE = {"id": "e1", "source": "app", "target": "page"}
CARD_EDGE = {"id": "e2", "source": "card", "target": "page"}


def graph(*nodes, edges=()):
    return {"nodes": list(nodes), "edges": list(edges)}


def site_graph(*extra, edges=(ARCH_EDGE, CARD_EDGE), app=None):
    return graph(app or domain(), page(), node("card", parent_id="page"), *extra, edges=edges)


def ids(items):
    return [item["id"] for item in items]


def put(s, pid, wid, content):
    write_workspace_graph(s.graph_file(pid, wid), encode(content))


def docs(s, pid, wid, node_id, table, values):
    with s.lock_for(pid):
        db = s.db_for(pid)
        with db:
            for revision, value in enumerate(values, 1):
                db.execute(f"INSERT INTO {table} VALUES(?,?,?,?,?,?)",
                           (pid, wid, node_id, revision, value, f"2026-10-0{revision}T00:00:00+00:00"))


def doc_rows(s, pid, wid, node_id, table):
    with s.reading(pid):
        return [tuple(row) for row in s.db_for(pid).execute(
            f"SELECT * FROM {table} WHERE project_id=? AND workspace_id=? AND node_id=? ORDER BY revision",
            (pid, wid, node_id))]


def local_project(tmp_path, content):
    s = CanvasService(tmp_path / "data")
    pid = s.project_hub.empty_project({"name": "Lokální", "confirmed": True})["id"]
    with s.lock_for(pid):
        db = s.db_for(pid)
        with db:
            db.execute("UPDATE drafts SET graph=? WHERE id=?", (encode(content), pid))
    return s, pid


def old_workspace(s, pid, actor):
    """Worktree jako před doménami (node_id = "project"); create_workspace dnes chce doménu z architektury."""
    repo = s.row("projects", pid)["repo"]
    base = git(repo, "rev-parse", "HEAD")
    wid, directory = s._new_worktree_folder(pid)
    git(repo, "worktree", "add", "-b", "work/" + wid, str(directory), base)
    with s.registry_lock, s.db:
        s.db.execute("INSERT INTO workspaces VALUES(?,?,?,?,?,?,?)",
                     (wid, pid, str(directory), "work/" + wid, "project", actor, base))
    return wid


@pytest.fixture
def git_project(tmp_path):
    s, p = managed_fixture(tmp_path)
    a = old_workspace(s, p["id"], "Agent A")
    b = old_workspace(s, p["id"], "Agent B")
    yield s, p["id"], *sorted([a, b])
    s.close()


def test_local_project_moves_domains_and_keeps_the_composed_view(tmp_path):
    s, pid = local_project(tmp_path, site_graph())
    before = s.view(pid, "draft")
    report = migrate(s, pid)
    assert report["phase"] == "dry-run" and report["backup"] is None
    assert [(m["id"], m["type"]) for m in report["moved"]] == [("app", "node"), ("page", "node"), ("e1", "edge")]
    assert report["moved"][0]["sources"] == [{"workspace": "draft", "origin": "draft"}]
    assert s.architecture.read(pid)["revision"] == 0 and s.view(pid, "draft")["digest"] == before["digest"]

    done = migrate(s, pid, dry_run=False)
    assert done["phase"] == "done" and done["backup"].startswith("architecture-")
    assert ids(s.architecture.read(pid)["graph"]["nodes"]) == ["app", "page"]
    assert s.architecture.history(pid)[0]["workspace"] == "migrace"
    with s.reading(pid):
        stored = json.loads(s.db_for(pid).execute("SELECT graph FROM drafts WHERE id=?", (pid,)).fetchone()[0])
    assert ids(stored["nodes"]) == ["card"] and ids(stored["edges"]) == ["e2"]
    after = s.view(pid, "draft")
    assert after["graph"] == before["graph"] and after["digest"] == before["digest"] and after["conflicts"] == []
    s.close()


def test_identical_worktree_copies_are_deduplicated_with_spec_history(git_project):
    s, pid, a, b = git_project
    put(s, pid, a, site_graph())
    put(s, pid, b, site_graph(node("other")))
    first, second = json.dumps({"goal": "v1"}), json.dumps({"goal": "v2"})
    docs(s, pid, a, "app", "node_spec_revisions", [first, second])
    docs(s, pid, b, "app", "node_spec_revisions", [second])
    docs(s, pid, b, "page", "node_text_revisions", ["text 1", "text 2", "text 3"])
    before = {wid: s.view(pid, wid) for wid in (a, b)}

    report = migrate(s, pid, dry_run=False)
    assert report["phase"] == "done" and report["conflicts"] == []
    assert report["moved"][0]["sources"] == [{"workspace": a, "origin": "data"}, {"workspace": b, "origin": "data"}]
    assert {(d["nodeId"], d["kind"], d["from"], d["revisions"], tuple(d["identicalIn"])) for d in report["docs"]} == {
        ("app", "spec", a, 2, (b,)), ("page", "text", b, 3, ())}
    for wid, extra in ((a, []), (b, ["other"])):
        stored = json.loads(s.graph_file(pid, wid).read_text(encoding="utf-8"))
        assert ids(stored["nodes"]) == ["card", *extra]
        view = s.view(pid, wid)
        assert view["graph"] == before[wid]["graph"] and view["digest"] == before[wid]["digest"]
    # Kopie i s historií a čísly revizí; zdrojové řádky zůstávají.
    assert [row[3:] for row in doc_rows(s, pid, "architecture", "app", "node_spec_revisions")] == [
        row[3:] for row in doc_rows(s, pid, a, "app", "node_spec_revisions")]
    assert len(doc_rows(s, pid, "architecture", "page", "node_text_revisions")) == 3
    assert len(doc_rows(s, pid, a, "app", "node_spec_revisions")) == 2
    assert s.node_spec(pid, b, "app")["fields"] == {"goal": "v2"}


def _conflicting(s, pid, a, b, case):
    put(s, pid, a, site_graph())
    if case == "content":
        put(s, pid, b, site_graph(app=domain(name="Jiná aplikace")))
    elif case == "kind":
        put(s, pid, b, graph(node("app", kind="sector")))
    elif case == "host":
        put(s, pid, b, graph(domain("other")))
    else:
        put(s, pid, b, site_graph())
        docs(s, pid, a, "page", "node_spec_revisions", [json.dumps({"goal": "A"})])
        docs(s, pid, b, "page", "node_spec_revisions", [json.dumps({"goal": "B"})])


@pytest.mark.parametrize("case", ["content", "kind", "host", "spec"])
def test_conflicting_copies_skip_the_project_and_write_nothing(git_project, case):
    s, pid, a, b = git_project
    _conflicting(s, pid, a, b, case)
    files = {wid: s.graph_file(pid, wid).read_bytes() for wid in (a, b)}
    for dry_run in (True, False):
        report = migrate(s, pid, dry_run=dry_run)
        assert report["phase"] == "conflicts" and report["backup"] is None
        assert {c["reason"] for c in report["conflicts"]} == {case}
        assert all(c["message"] for c in report["conflicts"])
    assert s.architecture.read(pid)["revision"] == 0
    assert {wid: s.graph_file(pid, wid).read_bytes() for wid in (a, b)} == files
    assert not (s.folder(pid).canvas / "backups").exists()


def test_head_and_legacy_worktree_file_are_sources(tmp_path):
    s, p = managed_fixture(tmp_path)
    pid = p["id"]
    main = Path(p["repo"])
    (main / "opora-canvas.json").write_text(encode(site_graph()), encoding="utf-8")
    git(main, "add", "opora-canvas.json")
    git(main, "-c", "user.name=F", "-c", "user.email=f@example.invalid", "commit", "-m", "graf")
    wid = old_workspace(s, pid, "Agent A")
    legacy = Path(s.location(pid, wid)[0]) / "opora-canvas.json"
    legacy_bytes = legacy.read_bytes()
    before = {w: s.view(pid, w) for w in ("main", wid)}

    report = migrate(s, pid, dry_run=False)
    assert report["phase"] == "done"
    assert report["moved"][0]["sources"] == [{"workspace": "main", "origin": "git"}, {"workspace": wid, "origin": "legacy"}]
    assert {(item["workspace"], item["action"]) for item in report["strip"]} == {("main", "read-only"), (wid, "legacy")}
    assert legacy.read_bytes() == legacy_bytes and not s.graph_file(pid, wid).exists()
    for w in ("main", wid):
        view = s.view(pid, w)
        assert view["graph"] == before[w]["graph"] and view["conflicts"] == []
    s.close()


def test_resume_after_crash_between_phases(git_project, monkeypatch):
    s, pid, a, _b = git_project
    put(s, pid, a, site_graph())
    docs(s, pid, a, "app", "node_spec_revisions", [json.dumps({"goal": "x"})])
    before = s.view(pid, a)

    def crash(*_args):
        raise RuntimeError("pád procesu")

    monkeypatch.setitem(module.STEPS, "strip", crash)
    with pytest.raises(RuntimeError):
        migrate(s, pid, dry_run=False)
    assert migrate(s, pid)["phase"] == "docs"
    assert s.architecture.read(pid)["revision"] == 1
    # Mezi fázemi je pohled pořád v pořádku: kopie architektury v obsahu se skryjí.
    middle = s.view(pid, a)
    assert middle["graph"] == before["graph"] and middle["conflicts"] == []
    monkeypatch.undo()

    done = migrate(s, pid, dry_run=False)
    assert done["phase"] == "done"
    assert s.architecture.read(pid)["revision"] == 1
    assert len(doc_rows(s, pid, "architecture", "app", "node_spec_revisions")) == 1
    assert ids(json.loads(s.graph_file(pid, a).read_text(encoding="utf-8"))["nodes"]) == ["card"]


def test_finished_migration_and_foreign_architecture_are_no_ops(git_project):
    s, pid, a, _b = git_project
    put(s, pid, a, site_graph())
    migrate(s, pid, dry_run=False)
    stored = s.graph_file(pid, a).read_bytes()
    again = migrate(s, pid, dry_run=False)
    assert again["phase"] == "done" and "už proběhla" in again["message"]
    assert s.architecture.read(pid)["revision"] == 1 and s.graph_file(pid, a).read_bytes() == stored


def test_architecture_created_outside_migration_is_left_alone(git_project):
    s, pid, a, _b = git_project
    current = s.view(pid, "main")
    s.save_graph(pid, "main", graph(domain()), current["digest"], actor="human")
    put(s, pid, a, site_graph(app=domain()))
    report = migrate(s, pid, dry_run=False)
    assert report["phase"] == "skipped" and "nezaložila ji migrace" in report["message"]
    assert s.architecture.read(pid)["revision"] == 1


def test_nothing_to_migrate(tmp_path):
    s, pid = local_project(tmp_path, graph(node("card")))
    assert migrate(s, pid, dry_run=False)["phase"] == "empty"
    assert not (s.folder(pid).canvas / "backups").exists()
    s.close()


def test_migrate_route_defaults_to_dry_run(tmp_path):
    from fastapi.testclient import TestClient

    from backend.app.factory import create_app
    from backend.canvas.test_canvas_plan import HEADERS, ORIGIN

    s = CanvasService(tmp_path / "data")
    s.view("draft", "draft")
    with s.lock_for("draft"):
        db = s.db_for("draft")
        with db:
            db.execute("UPDATE drafts SET graph=? WHERE id='draft'", (encode(site_graph()),))
    s.close()
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        url = "/api/project-architecture/migrate"
        preview = client.post(url, headers=HEADERS, json={"project": "draft"})
        assert preview.status_code == 200, preview.text
        assert preview.json()["phase"] == "dry-run" and preview.json()["backup"] is None
        assert client.post(url, headers=HEADERS, json={"project": "draft", "dryRun": "ne"}).status_code == 409
        done = client.post(url, headers=HEADERS, json={"project": "draft", "dryRun": False}).json()
        assert done["phase"] == "done" and [m["id"] for m in done["moved"]] == ["app", "page", "e1"]
        assert "architecture" not in done
