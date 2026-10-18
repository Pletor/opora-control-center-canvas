"""Workspace snapshots cover content, reject stale writers, and roll back failed restores."""
import json

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.graph import digest as graph_digest
from backend.editor.canvas_versions.test_canvas_versions import digest, graph, save, versions
from backend.editor.canvas_versions.version_content import STORES, empty_data, read_records
from backend.editor.node.test_removals import (
    HEADERS,
    ORIGIN,
    SCOPE,
    desktop_state,
    install_desktop_state,
    install_graph,
    state_node,
)


def seed(db, name, data, revision=1, key=None, workspace="draft"):
    table, keys, columns = STORES[name]
    key = key or (["a", "2026-10-05"] if name == "journals" else [""] if name == "documents"
                  else ["a", 1] if name == "cardRounds" else ["a"])
    p, w = ("project", "workspace") if name == "documents" else ("project_id", "workspace_id")
    names = (p, w, *keys, "revision", *columns, "saved_at")
    values = [json.dumps(data[col]) if col in {"fields", "scene", "sections", "record"} else data[col] for col in columns]
    db.execute(f"INSERT OR REPLACE INTO {table}({','.join(names)}) VALUES({','.join('?' for _ in names)})",
               ("draft", workspace, *key, revision, *values, "2026-10-05T10:00:00Z"))
    db.commit()


def contents(marker):
    items = {name: empty_data(name) for name in STORES}
    items["specs"]["fields"]["goal"] = marker
    items["texts"]["text"] = items["journals"]["text"] = marker
    items["agentWorkspaces"]["sections"]["handoff"] = marker
    items["documents"]["fields"]["purpose"] = marker
    items["briefFragments"].update(text=marker, title=marker, deleted=0, scope_node_id="")
    items["briefDetails"]["fields"] = {"decisions": [marker]}
    items["cardRounds"]["record"] = {"schema": "opora.card-round/1", "nodeId": "a", "round": 1, "openReason": marker}
    items["briefLessons"].update(text=marker, fragment_id="f", cycle_revision=3, discipline="be", weight=1.0, dropped=0,
                                 created_at="2026-10-05T10:00:00+00:00", confirmed_at="2026-10-05T10:00:00+00:00")
    items["drawings"]["scene"]["elements"] = [{"id": "rect", "type": "rectangle", "x": 0, "y": 0,
                                                "width": 10 if marker == "before" else 20, "height": 10}]
    return items


def bound_restore(client, version_id, token=None):
    return client.post("/api/canvas-versions/restore", headers=HEADERS, json={**SCOPE,
        "versionId": version_id, "digest": digest(client), "author": "test",
        "expectedToken": token or versions(client)["currentToken"]})


def test_all_stores_round_trip_and_revisions_advance_without_touching_other_workspace(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        install_graph(client, graph("a"))
        db = app.state.service.db_for("draft")
        for name, data in contents("before").items():
            seed(db, name, data)
            seed(db, name, data, workspace="other")
        saved = save(client).json()["version"]
        immutable = client.get("/api/canvas-versions", params={**SCOPE, "versionId": saved["id"]}).json()
        assert immutable["integrity"] == "verified" and immutable["version"]["coverage"] == "full"
        assert immutable["snapshot"]["projectGoal"]["restore"] is False
        for name, data in contents("after").items():
            seed(db, name, data, 2)
        seed(db, "texts", {"text": "new since checkpoint"}, key=["later"])
        result = bound_restore(client, saved["id"])
        assert result.status_code == 200, result.text
        restored = read_records(db, "draft", "draft")
        for name, data in contents("before").items():
            row = next(row for row in restored[name] if row["key"][0] != "later")
            assert row["data"] == data and row["revision"] == 3
            assert read_records(db, "draft", "other")[name][0]["revision"] == 1
        assert next(row for row in restored["texts"] if row["key"] == ["later"])["data"] == {"text": ""}
        assert versions(client)["dirty"] is False
        assert client.get("/api/canvas-versions", params={**SCOPE, "versionId": saved["id"]}).json() == immutable


@pytest.mark.parametrize("store", [*STORES, "desktop", "settings"])
def test_any_covered_revision_or_goal_context_change_rejects_stale_save_and_restore(tmp_path, store):
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        install_graph(client, graph("a"))
        saved = save(client).json()["version"]
        observed = versions(client)["currentToken"]
        db = app.state.service.db_for("draft")
        if store == "desktop":
            install_desktop_state(client, desktop_state(nodes={"a": state_node()}))
        elif store == "settings":
            db.execute("INSERT INTO project_settings VALUES('draft',1,'changed goal','web')")
            db.commit()
        else:
            seed(db, store, contents("after")[store])
        before = list(db.iterdump())
        result = bound_restore(client, saved["id"], observed)
        assert result.status_code == 409, result.text
        result = client.post("/api/canvas-versions", headers=HEADERS, json={**SCOPE,
            "digest": digest(client), "author": "test", "expectedToken": observed})
        assert result.status_code == 409 and list(db.iterdump()) == before


def test_restore_exception_rolls_back_graph_content_and_recovery_checkpoint(tmp_path, monkeypatch):
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        install_graph(client, graph("a"))
        service = app.state.service
        db = service.db_for("draft")
        seed(db, "texts", {"text": "before"})
        saved = save(client).json()["version"]
        install_graph(client, graph("a", "b"))
        seed(db, "texts", {"text": "after"}, 2)
        before = list(db.iterdump())
        original = service.save_graph
        def fail_after_graph(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("injected after graph write")
        monkeypatch.setattr(service, "save_graph", fail_after_graph)
        with pytest.raises(RuntimeError, match="injected"):
            bound_restore(client, saved["id"])
        assert list(db.iterdump()) == before
        assert [item["id"] for item in service.view("draft", "draft")["graph"]["nodes"]] == ["a", "b"]


def test_legacy_snapshot_is_explicitly_partial_and_shared_settings_never_restore(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        install_graph(client, graph("a"))
        saved = save(client).json()["version"]
        db = app.state.service.db_for("draft")
        db.execute("UPDATE canvas_versions SET snapshot=NULL,content_digest=NULL WHERE id=?", (saved["id"],))
        db.execute("INSERT INTO project_settings VALUES('draft',8,'keep shared goal','app')")
        db.commit()
        seed(db, "texts", {"text": "keep legacy-excluded content"})
        result = bound_restore(client, saved["id"])
        assert result.status_code == 200 and result.json()["coverage"] == "legacy-partial"
        assert db.execute("SELECT revision,goal,platform FROM project_settings").fetchone()[:] == (8, "keep shared goal", "app")
        assert read_records(db, "draft", "draft")["texts"][0]["data"]["text"] == "keep legacy-excluded content"


def test_snapshot_integrity_failure_precedes_all_writes(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        install_graph(client, graph("a"))
        saved = save(client).json()["version"]
        db = app.state.service.db_for("draft")
        db.execute("UPDATE canvas_versions SET state_digest=? WHERE id=?", (graph_digest({}), saved["id"]))
        db.commit()
        before = list(db.iterdump())
        result = bound_restore(client, saved["id"])
        assert result.status_code == 409 and list(db.iterdump()) == before
