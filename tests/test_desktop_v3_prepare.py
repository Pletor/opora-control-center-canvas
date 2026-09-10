"""Příprava dokumentačního běhu nad PŘESNÝM snapshotem; žádné automatické spuštění."""
import hashlib
import json

from fastapi.testclient import TestClient
from test_desktop_v3_packets import HEADERS, ORIGIN, preview, request, seed

from backend.app import create_app
from backend.llm_runs import _canonical
from backend.task_handoff_tools import DocumentTools


def _snapshot(client, scope):
    seen = preview(client, scope).json()
    stored = client.post("/api/desktop-v3/packet/snapshot", headers=HEADERS, json={**request(scope), "digest": seen["digest"]})
    assert stored.status_code == 200, stored.text
    return stored.json()


def _prepare(client, scope, snapshot, task="Sepiš dokumentaci uzlu podle balíčku."):
    return client.post(f"/api/desktop-v3/packet/snapshots/{snapshot['id']}/prepare", headers=HEADERS, json={**scope, "task": task})


def test_prepare_returns_existing_handoff_format_over_exact_snapshot_and_does_not_start(tmp_path):
    app = create_app(tmp_path / "data")
    with TestClient(app, base_url=ORIGIN) as client:
        scope = seed(client, tmp_path)
        snapshot = _snapshot(client, scope)
        prepared = _prepare(client, scope, snapshot)
        assert prepared.status_code == 200, prepared.text
        record = prepared.json()
        assert set(record) == {"id", "digest", "scope", "task", "allowedFiles", "readableNodeIds", "contextSummary", "provider", "model", "budgetSeconds", "status", "events", "verification", "result", "error", "localTreeInactive"}
        assert record["status"] == "prepared" and record["events"] == []
        assert record["scope"] == {"project": scope["project"], "workspace": "draft", "node": "focus"}
        assert record["allowedFiles"] == ["result.md"]
        assert record["readableNodeIds"] == ["focus", "parent", "sector"]
        assert record["contextSummary"]["snapshotId"] == snapshot["id"]
        assert record["contextSummary"]["packetDigest"] == snapshot["digest"]
        assert record["contextSummary"]["sourceManifest"] == snapshot["packet"]["sourceManifest"]
        listed = client.get("/api/task-handoffs", params=scope).json()["runs"]
        assert [item["id"] for item in listed] == [record["id"]]
        assert listed[0]["status"] == "prepared"
        assert client.get(f"/api/task-handoffs/{record['id']}").json()["digest"] == record["digest"]
        exported = client.get(f"/api/task-handoffs/{record['id']}/export").json()
        assert exported["context"]["documents"] == snapshot["packet"]
        assert exported["context"]["map"]["snapshotId"] == snapshot["id"]
        assert "workspacePath" not in exported
        handoffs = app.state.task_handoffs
        stored = handoffs._record(record["id"])
        assert stored["pid"] is None and stored["status"] == "prepared"
        assert stored["contextDigest"] == hashlib.sha256(_canonical(stored["context"]).encode("utf-8")).hexdigest()
        tools = DocumentTools(tmp_path, stored["context"])
        assert tools.read_context("documents") == snapshot["packet"]
        assert tools.read_context("map")["digest"] == snapshot["digest"]
        assert not (tmp_path / "data" / "task-handoff-workspaces" / record["id"]).exists()
        assert not (tmp_path / "data" / "task-handoff-runs" / record["id"]).exists()


def test_worker_file_carries_the_same_snapshot_bytes(tmp_path):
    app = create_app(tmp_path / "data")
    with TestClient(app, base_url=ORIGIN) as client:
        scope = seed(client, tmp_path)
        snapshot = _snapshot(client, scope)
        record = _prepare(client, scope, snapshot).json()
        handoffs = app.state.task_handoffs
        stored = handoffs._record(record["id"])
        settings = handoffs._settings(scope["project"])[0]
        _path, packet_path, packet = handoffs._initialize_workspace(record["id"], stored, settings)
        written = json.loads(packet_path.read_text(encoding="utf-8"))
        assert written["context"]["documents"] == snapshot["packet"]
        assert _canonical(written["context"]["documents"]) == _canonical(snapshot["packet"])
        assert packet["task"] == "Sepiš dokumentaci uzlu podle balíčku."
        assert handoffs.get(record["id"])["status"] == "prepared"


def test_prepare_guards_scope_task_main_and_start_digest(tmp_path):
    app = create_app(tmp_path / "data")
    with TestClient(app, base_url=ORIGIN) as client:
        scope = seed(client, tmp_path)
        snapshot = _snapshot(client, scope)
        other = client.post("/api/empty-project", headers=HEADERS, json={"name": "Other", "confirmed": True}).json()["id"]
        assert _prepare(client, {"project": other, "workspace": "draft"}, snapshot).status_code == 409
        assert _prepare(client, scope, snapshot, task="   ").status_code == 409
        assert _prepare(client, scope, snapshot, task="x" * 4001).status_code == 409
        assert client.post(f"/api/desktop-v3/packet/snapshots/{snapshot['id']}/prepare", headers=HEADERS, json={**scope, "task": "ok", "extra": True}).status_code == 409
        assert client.post("/api/desktop-v3/packet/snapshots/missing/prepare", headers=HEADERS, json={**scope, "task": "ok"}).status_code == 409
        record = _prepare(client, scope, snapshot).json()
        wrong = client.post(f"/api/task-handoffs/{record['id']}/start", headers=HEADERS, json={"digest": "0" * 64, "confirmed": True})
        assert wrong.status_code == 409
        unconfirmed = client.post(f"/api/task-handoffs/{record['id']}/start", headers=HEADERS, json={"digest": record["digest"], "confirmed": False})
        assert unconfirmed.status_code == 409
        assert client.get(f"/api/task-handoffs/{record['id']}").json()["status"] == "prepared"


def test_start_refuses_when_snapshot_sources_changed(tmp_path):
    app = create_app(tmp_path / "data")
    with TestClient(app, base_url=ORIGIN) as client:
        scope = seed(client, tmp_path)
        snapshot = _snapshot(client, scope)
        record = _prepare(client, scope, snapshot).json()
        state = client.get("/api/desktop-v3/state", params=scope).json()
        state["state"]["rules"].append({"id": "r9", "text": "Nové pravidlo.", "kind": "must", "scope": "project", "target": ""})
        assert client.post("/api/desktop-v3/state", headers=HEADERS, json={**scope, "expectedRevision": state["revision"], "state": state["state"]}).status_code == 200
        refused = client.post(f"/api/task-handoffs/{record['id']}/start", headers=HEADERS, json={"digest": record["digest"], "confirmed": True})
        assert refused.status_code == 409, refused.text
        assert "změn" in refused.json()["error"].lower()
        current = client.get(f"/api/task-handoffs/{record['id']}").json()
        assert current["status"] == "prepared" and current["events"] == []
        assert client.get(f"/api/desktop-v3/packet/snapshots/{snapshot['id']}", params=scope).json()["packet"] == snapshot["packet"]
