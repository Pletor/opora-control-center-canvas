"""Opt-in Git graph storage across ordinary edits, restart and version restoration."""
import copy

import pytest

from backend.canvas.canvas_service import CanvasService
from backend.canvas.graph import EMPTY
from backend.canvas.migrate_architecture import migrate
from backend.canvas.migrate_architecture_backup import down, new_backup_id, take_backup
from backend.canvas.test_workspace_graph import GRAPH, repository, workspace
from backend.canvas.test_migrate_architecture import site_graph
from backend.editor.canvas_versions.canvas_versions import CanvasVersions
from backend.project.worktrees.test_workspace_archive import Sessions
from backend.project.worktrees.workspace_archive import WorkspaceArchive
from database.repositories.workspace_graph_authority import WorkspaceGraphAuthority
from database.schema.project_initialization import initialize_project_schema


@pytest.fixture
def enrolled(tmp_path):
    data = tmp_path / "data"
    service = CanvasService(data)
    project, wid, _directory = workspace(service, repository(tmp_path, data))
    view = service.view(project, wid)
    service.save_graph(project, wid, GRAPH, view["digest"])
    original = service.graph_file(project, wid).read_bytes()
    db = service.db_for(project)
    db.execute("BEGIN IMMEDIATE")
    WorkspaceGraphAuthority(db, project, wid).enroll(GRAPH)
    db.commit()
    yield service, project, wid, original, data
    service.close()


def test_normal_edits_read_database_after_restart_without_touching_file(enrolled):
    service, project, wid, original, data = enrolled
    graph = copy.deepcopy(GRAPH)
    graph["nodes"][1]["name"] = "Updated authority"
    service.save_graph(project, wid, graph, service.view(project, wid)["digest"])
    assert service.graph_file(project, wid).read_bytes() == original
    assert service.view(project, wid)["graph"] == graph
    fresh = CanvasService(data)
    try:
        assert fresh.view(project, wid)["graph"] == graph
        assert fresh.view(project, "main")["graph"] == EMPTY
    finally:
        fresh.close()


def test_canvas_version_restore_keeps_authority_and_original_file(enrolled):
    service, project, wid, original, _data = enrolled
    versions = CanvasVersions(service)
    scope = {"project": project, "workspace": wid, "author": "test"}
    saved = versions.save({**scope, "digest": service.view(project, wid)["digest"]})
    graph = copy.deepcopy(GRAPH)
    graph["nodes"][1]["name"] = "New working content"
    service.save_graph(project, wid, graph, service.view(project, wid)["digest"])
    versions.restore({**scope, "versionId": saved["version"]["id"],
                      "digest": service.view(project, wid)["digest"],
                      "expectedToken": versions.head(project, wid)["currentToken"]})
    assert service.view(project, wid)["graph"] == GRAPH
    assert service.graph_file(project, wid).read_bytes() == original
    assert WorkspaceGraphAuthority(service.db_for(project), project, wid).read()["revision"] == 3


@pytest.mark.parametrize("force", [False, True])
def test_architecture_backup_restore_refuses_enrolled_scope_even_forced(enrolled, force):
    service, project, _wid, _original, _data = enrolled
    with pytest.raises(ValueError, match="restore is unavailable"):
        down(service, project, "architecture-20261021T010000Z-12345678", force=force)


def test_corrupt_authority_does_not_return_valid_stale_file(enrolled):
    service, project, wid, original, _data = enrolled
    db = service.db_for(project)
    db.execute("UPDATE workspace_graph_authority SET digest='corrupt'")
    db.commit()
    with pytest.raises(ValueError, match="corrupt"):
        service.view(project, wid)
    assert service.graph_file(project, wid).read_bytes() == original


def test_old_backup_reinitializes_schema_on_same_cached_connection(tmp_path):
    data = tmp_path / "data"
    service = CanvasService(data)
    try:
        project, wid, _directory = workspace(service, repository(tmp_path, data))
        db = service.db_for(project)
        db.execute("DROP TABLE workspace_graph_authority")
        db.execute("DROP TABLE opora_execution_epochs")
        db.commit()
        identifier = new_backup_id()
        take_backup(service, project, [wid], identifier)
        initialize_project_schema(db)
        db.commit()
        down(service, project, identifier, force=True)
        assert service.db_for(project) is db
        assert WorkspaceGraphAuthority(db, project, wid).read() is None
        assert db.execute("SELECT count(*) FROM opora_execution_epochs").fetchone()[0] == 0
        service.save_graph(project, wid, GRAPH, service.view(project, wid)["digest"])
        db.execute("BEGIN IMMEDIATE")
        WorkspaceGraphAuthority(db, project, wid).enroll(GRAPH)
        db.commit()
        assert service.view(project, wid)["graph"] == GRAPH
    finally:
        service.close()


def test_execution_only_backup_refusal_happens_before_any_restore(tmp_path, monkeypatch):
    data = tmp_path / "data"
    service = CanvasService(data)
    try:
        project, wid, _directory = workspace(service, repository(tmp_path, data))
        db = service.db_for(project)
        db.execute("INSERT INTO opora_execution_epochs VALUES(?,?,?,?)", (project, wid, "card", 9))
        db.commit()

        def fail(*args):
            pytest.fail("Restore touched backup files before enrollment guard")

        monkeypatch.setattr("backend.canvas.migrate_architecture_backup.read_manifest", fail)
        with pytest.raises(ValueError, match="after execution enrollment"):
            down(service, project, "architecture-20261021T010000Z-12345678", force=True)
        assert db.execute("SELECT epoch FROM opora_execution_epochs").fetchone()[0] == 9
    finally:
        service.close()


def test_local_accepted_history_blocks_backup_before_reading_files(tmp_path, monkeypatch):
    service = CanvasService(tmp_path / "data")
    try:
        db = service.db_for("draft")
        db.execute("INSERT INTO opora_spec_refs VALUES('draft','draft','accepted')")
        db.commit()
        assert WorkspaceGraphAuthority(db, "draft", "draft").read() is None

        def fail(*args):
            pytest.fail("Accepted history was not guarded before reading backup")

        monkeypatch.setattr("backend.canvas.migrate_architecture_backup.read_manifest", fail)
        with pytest.raises(ValueError, match="after accepted plan history"):
            down(service, "draft", "architecture-20261021T010000Z-12345678", force=True)
        assert db.execute("SELECT accepted_id FROM opora_spec_refs").fetchone()[0] == "accepted"
    finally:
        service.close()


def test_architecture_migration_strips_authority_without_touching_legacy_file(enrolled):
    service, project, wid, original, _data = enrolled
    db = service.db_for(project)
    db.execute("BEGIN IMMEDIATE")
    WorkspaceGraphAuthority(db, project, wid).write(site_graph())
    db.commit()
    report = migrate(service, project, dry_run=False)
    assert report["phase"] == "done"
    stored = WorkspaceGraphAuthority(db, project, wid).read()
    assert [node["id"] for node in stored["graph"]["nodes"]] == ["card"]
    assert {node["id"] for node in service.view(project, wid)["graph"]["nodes"]} == {"app", "page", "card"}
    assert service.graph_file(project, wid).read_bytes() == original


def test_archive_keeps_authoritative_graph_and_serializes_graph_mutations(enrolled, monkeypatch):
    service, project, wid, original, _data = enrolled
    archive = WorkspaceArchive(service, Sessions())
    original_move = archive._move_data

    def checked_move(pid, workspace_id):
        assert service.graph_lock_for(pid)._is_owned()
        assert service.lock_for(pid)._is_owned()
        return original_move(pid, workspace_id)

    monkeypatch.setattr(archive, "_move_data", checked_move)
    archive.archive(wid, {"project": project, "reason": "test archive", "confirmed": True})
    assert WorkspaceGraphAuthority(service.db_for(project), project, wid).read()["graph"] == GRAPH
    archived = service.graph_file(project, wid).parent.parent / "_archive" / wid / "graph.json"
    assert archived.read_bytes() == original
    assert archive.items(project)["items"][0]["id"] == wid
