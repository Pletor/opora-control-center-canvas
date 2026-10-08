import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.agent_memory.test_completion_evidence import evidence
from backend.canvas.graph import encode
from backend.editor.agent_memory.desktop_v3_state import default_done
from backend.editor.canvas_versions.canvas_versions import CanvasVersions
from backend.editor.canvas_versions.test_canvas_versions import digest, graph, save, versions
from backend.editor.canvas_versions.test_version_content import bound_restore, seed
from backend.editor.node.test_removals import HEADERS, ORIGIN, SCOPE, desktop_state, install_desktop_state, install_graph, state_block, state_node
from database.schema.project_schema import ensure_canvas_version_columns


def test_restore_requires_token_even_with_fresh_graph_digest(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        install_graph(client, graph("a"))
        saved = save(client).json()["version"]
        db = app.state.service.db_for("draft")
        before = list(db.iterdump())
        response = client.post("/api/canvas-versions/restore", headers=HEADERS, json={**SCOPE,
            "versionId": saved["id"], "digest": digest(client), "author": "test"})
        assert response.status_code == 409 and "expectedToken" in response.json()["error"]
        assert list(db.iterdump()) == before


def test_attachment_and_drawing_bytes_survive_removal_and_restore(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        install_graph(client, graph("a"))
        service = app.state.service
        db = service.db_for("draft")
        filename = "20261005-101010-12345678.png"
        path = service.folder("draft").canvas / "materials" / "a" / filename
        path.parent.mkdir(parents=True)
        path.write_bytes(b"uploaded-image")
        install_desktop_state(client, desktop_state(nodes={"a": state_node(materials=[{
            "id": "material", "kind": "upload", "path": filename, "caption": "reference"}])}))
        scene = {"elements": [{"id": "image", "type": "image", "fileId": "file1", "x": 0, "y": 0, "width": 10, "height": 10}]}
        seed(db, "drawings", {"scene": scene})
        db.execute("INSERT INTO drawing_files VALUES('draft','file1','image/png',?,'now')", (b"drawing-image",))
        db.commit()
        saved = save(client).json()["version"]
        path.unlink()
        db.execute("DELETE FROM drawing_files")
        db.commit()
        assert versions(client)["dirty"] is True
        response = bound_restore(client, saved["id"])
        assert response.status_code == 200, response.text
        assert path.read_bytes() == b"uploaded-image"
        assert db.execute("SELECT data FROM drawing_files").fetchone()[0] == b"drawing-image"
        assert versions(client)["dirty"] is False


def test_closed_blocks_and_invalid_phase_restore_reject_before_graph_write(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        install_graph(client, graph("a"))
        closed = {**default_done(), "confirmed": True, "at": "2026-10-05T00:00:00Z"}
        old = desktop_state(nodes={"a": state_node(blocks=[state_block()], done=closed, evidence=evidence())})
        install_desktop_state(client, old)
        saved = save(client).json()["version"]
        install_graph(client, graph("a", "b"))
        db = app.state.service.db_for("draft")
        changed = json.loads(json.dumps(old))
        changed["nodes"]["a"]["blocks"][0]["text"] = "changed while reopened, then closed again"
        db.execute("UPDATE desktop_v3_state SET revision=4,state=?", (encode(changed),))
        db.commit()
        before = list(db.iterdump())
        response = bound_restore(client, saved["id"])
        assert response.status_code == 409 and "Uzavřená karta" in response.json()["error"]
        assert list(db.iterdump()) == before


def test_phase_gate_has_explicit_no_write_failure_for_historical_forward_restore(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        install_graph(client, graph("a"))
        # A newly-created card may have an advanced phase with no criteria.
        install_desktop_state(client, desktop_state(nodes={"a": state_node(phase="define")}))
        saved = save(client).json()["version"]
        db = app.state.service.db_for("draft")
        db.execute("UPDATE desktop_v3_state SET revision=2,state=?", (encode(desktop_state(nodes={"a": state_node()})),))
        db.commit()
        before = list(db.iterdump())
        response = bound_restore(client, saved["id"])
        assert response.status_code == 409 and "pravidlům pracovního postupu" in response.json()["error"]
        assert list(db.iterdump()) == before


def test_git_file_and_database_roll_back_together_after_file_write_failure(tmp_path, monkeypatch):
    app = create_app(tmp_path / "data")
    service = app.state.service
    repo, work = tmp_path / "repo", tmp_path / "work"
    work.mkdir()
    service.register_repository("p", "Project", str(repo), "fixture://p", "main")
    service.db.execute("INSERT INTO workspaces VALUES(?,?,?,?,?,?,?)", ("work", "p", str(work), "work/test", "a", "Test", "base"))
    service.db.commit()
    monkeypatch.setattr("backend.canvas.canvas_service.git", lambda _root, *args, **kwargs: "a" * 40 if args == ("rev-parse", "HEAD") else "work/test" if args == ("branch", "--show-current") else None)
    scope = {"project": "p", "workspace": "work"}
    with TestClient(app, base_url=ORIGIN):
        store = CanvasVersions(service)
        path = work / "opora-canvas.json"
        path.write_text(encode(graph("a")), encoding="utf-8")
        saved = store.save({**scope, "digest": service.view("p", "work")["digest"], "author": "test"})["version"]
        path.write_text(encode(graph("a", "b")), encoding="utf-8")
        original_bytes = path.read_bytes()
        db = service.db_for("p")
        before = list(db.iterdump())
        token = store.list("p", "work")["currentToken"]
        original = service.save_graph
        def failure(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("after file replace")
        monkeypatch.setattr(service, "save_graph", failure)
        with pytest.raises(RuntimeError, match="file replace"):
            store.restore({**scope, "digest": service.view("p", "work")["digest"], "versionId": saved["id"], "author": "test", "expectedToken": token})
        assert path.read_bytes() == original_bytes and list(db.iterdump()) == before


def test_additive_migration_preserves_legacy_rows():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE canvas_versions(id TEXT PRIMARY KEY, graph TEXT)")
    db.execute("INSERT INTO canvas_versions VALUES('old','original')")
    ensure_canvas_version_columns(db)
    ensure_canvas_version_columns(db)
    assert db.execute("SELECT * FROM canvas_versions").fetchone() == ("old", "original", None, None)
    db.close()
