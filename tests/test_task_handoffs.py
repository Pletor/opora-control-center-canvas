import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.agents.runs.task_handoff_tools import DocumentTools

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
FIELDS = {"purpose", "goal", "architecture", "technologies", "notes", "requirements"}


def _seed_packet(client):
    view = client.get("/api/view?project=draft&workspace=draft").json()
    graph = {
        "nodes": [
            {
                "id": "sector",
                "parentId": None,
                "kind": "sector",
                "name": "Sektor",
                "purpose": "Dokumentace",
                "x": 0,
                "y": 0,
            },
            {
                "id": "focus",
                "parentId": "sector",
                "kind": "node",
                "name": "Ohnisko",
                "purpose": "Cíl",
                "x": 0,
                "y": 0,
            },
        ],
        "edges": [{"id": "relation", "source": "sector", "target": "focus"}],
    }
    assert (
        client.post(
            "/api/graph",
            headers=HEADERS,
            json={
                "project": "draft",
                "workspace": "draft",
                "graph": graph,
                "digest": view["digest"],
            },
        ).status_code
        == 200
    )
    packet = client.post(
        "/api/context/packets",
        headers=HEADERS,
        json={
            "project": "draft",
            "workspace": "draft",
            "node": "focus",
            "includeNodeIds": [],
            "includeJournalDays": [],
            "maxBytes": 50000,
        },
    )
    assert packet.status_code == 200
    return packet.json()


def _prepare(client, packet=None):
    packet = packet or _seed_packet(client)
    response = client.post(
        "/api/task-handoffs/prepare",
        headers=HEADERS,
        json={"packetId": packet["id"], "task": "Napiš stručný přehled."},
    )
    assert response.status_code == 200
    return response.json()


def _document_fields(notes="poznámka"):
    return {field: notes if field == "notes" else "" for field in FIELDS}


def _save_root_document(client, notes="kořenová dokumentace"):
    current = client.get("/api/workspace/document?project=draft&workspace=draft&path=").json()
    response = client.post(
        "/api/workspace/document",
        headers=HEADERS,
        json={
            "project": "draft",
            "workspace": "draft",
            "path": "",
            "expectedRevision": current["revision"],
            "expectedSettingsRevision": current["settingsRevision"],
            "fields": _document_fields(notes),
            "nodeId": "focus",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_prepare_persists_immutable_document_scope_from_saved_packet(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        packet = _seed_packet(client)
        prepared = _prepare(client, packet)
        assert prepared["status"] == "prepared"
        assert prepared["scope"] == {"project": "draft", "workspace": "draft", "node": "focus"}
        assert prepared["allowedFiles"] == ["result.md"]
        assert prepared["readableNodeIds"] == ["focus"]
        assert prepared["contextSummary"]["packetId"] == packet["id"]
        assert (
            client.get(f"/api/task-handoffs/{prepared['id']}").json()["digest"]
            == prepared["digest"]
        )


def test_export_is_redacted_worker_snapshot_and_stale_packet_refuses_start(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        packet = _seed_packet(client)
        prepared = _prepare(client, packet)
        exported = client.get(f"/api/task-handoffs/{prepared['id']}/export")
        assert exported.status_code == 200
        assert exported.json()["context"]["documents"] == packet["content"]
        assert "workspacePath" not in exported.json()
        view = client.get("/api/view?project=draft&workspace=draft").json()
        changed = {
            **view["graph"],
            "nodes": [
                {**node, "purpose": "Změněný cíl"} if node["id"] == "focus" else node
                for node in view["graph"]["nodes"]
            ],
        }
        assert (
            client.post(
                "/api/graph",
                headers=HEADERS,
                json={
                    "project": "draft",
                    "workspace": "draft",
                    "graph": changed,
                    "digest": view["digest"],
                },
            ).status_code
            == 200
        )
        refused = client.post(
            f"/api/task-handoffs/{prepared['id']}/start",
            headers=HEADERS,
            json={"digest": prepared["digest"], "confirmed": True},
        )
        assert refused.status_code == 409


def test_document_tools_only_read_snapshots_and_write_regular_result(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    tools = DocumentTools(root, {"map": {"nodes": []}, "documents": {"focus": {"text": "A"}}})
    assert tools.read_context("map") == {"nodes": []}
    written = tools.write_result("# Výsledek\n")
    assert written["path"] == "result.md"
    assert (root / "result.md").read_text(encoding="utf-8") == "# Výsledek\n"


def test_document_tools_refuse_dangling_result_link_and_rebound_root_without_outside_write(
    tmp_path,
):
    root, outside = tmp_path / "workspace", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    tools = DocumentTools(root, {"map": {}, "documents": {}})
    try:
        (root / "result.md").symlink_to(outside / "escaped.md")
    except OSError:
        pytest.skip("Windows symlink creation is unavailable in this test token")
    try:
        tools.write_result("# no")
    except ValueError:
        pass
    else:
        raise AssertionError("dangling result link must be refused")
    assert not (outside / "escaped.md").exists()
    (root / "result.md").unlink()
    moved = tmp_path / "old-workspace"
    root.rename(moved)
    root.symlink_to(outside, target_is_directory=True)
    try:
        tools.write_result("# no")
    except ValueError:
        pass
    else:
        raise AssertionError("rebound root must be refused")
    assert not (outside / "result.md").exists()


def test_document_tools_use_utf8_byte_bound_not_character_bound(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    tools = DocumentTools(root, {"map": {}, "documents": {}})
    try:
        tools.write_result("é" * 32001)
    except ValueError:
        pass
    else:
        raise AssertionError("UTF-8 byte overflow must be refused")


def test_document_tools_refuse_root_replacement_after_construction(tmp_path):
    root, replacement = tmp_path / "workspace", tmp_path / "replacement"
    root.mkdir()
    replacement.mkdir()
    tools = DocumentTools(root, {"map": {}, "documents": {}})
    root.rename(tmp_path / "moved-workspace")
    replacement.rename(root)
    with pytest.raises(ValueError):
        tools.write_result("# no")
    assert not (root / "result.md").exists()


def test_prepare_exports_bounded_workspace_documents_and_safe_map_relations(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        packet = _seed_packet(client)
        _save_root_document(client, "github_pat_abcdefghijklmnopqrstuvwxyz-secret")
        prepared = _prepare(client, packet)
        context = client.get(f"/api/task-handoffs/{prepared['id']}/export").json()["context"]
        root = context["workspaceDocuments"]["items"]["root"]
        assert root["path"] == ""
        assert root["nodeId"] == "focus"
        assert "[REDACTED]" in root["fields"]["notes"]
        assert context["map"]["nodes"] == [
            {
                "id": "focus",
                "parentId": "sector",
                "kind": "node",
                "name": "Ohnisko",
                "purpose": "Cíl",
            }
        ]
        assert context["map"]["edges"] == []
        assert "workspaceDocuments" in context


def test_start_refuses_changed_saved_document_even_when_packet_digest_is_unchanged(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        packet = _seed_packet(client)
        _save_root_document(client, "verze jedna")
        prepared = _prepare(client, packet)
        _save_root_document(client, "verze dvě")
        refused = client.post(
            f"/api/task-handoffs/{prepared['id']}/start",
            headers=HEADERS,
            json={"digest": prepared["digest"], "confirmed": True},
        )
        assert refused.status_code == 409


class _ShortChildPlans:
    def __init__(self, mode="success"):
        self.mode = mode

    def _hermes_paths(self):
        return (Path(sys.executable), Path.cwd(), Path(sys.executable))

    def list(self):
        return {"active": False}

    def _spawn(self, command):
        packet_path = command[-1]
        body = (
            "import json,sys,time; from pathlib import Path; "
            "p=json.loads(Path(sys.argv[1]).read_text()); "
            + (
                "Path(p['workspacePath'],'result.md').write_text('\\n \\t', encoding='utf-8')"
                if self.mode == "whitespace"
                else "time.sleep(1)"
                if self.mode == "slow"
                else "Path(p['workspacePath'],'result.md').write_text('# child result\\n', encoding='utf-8')"
            )
        )
        process = subprocess.Popen(
            [sys.executable, "-c", body, packet_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        return process, None

    @staticmethod
    def _tree_inactive(process, _job):
        return process.poll() is not None

    @staticmethod
    def _terminate(_handoff_id, process, _job):
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)
        return process.poll() is not None


def _wait_for(client, handoff_id, status, timeout=4):
    until = time.monotonic() + timeout
    latest = None
    while time.monotonic() < until:
        latest = client.get(f"/api/task-handoffs/{handoff_id}").json()
        if latest["status"] == status:
            return latest
        time.sleep(0.03)
    raise AssertionError(f"timed out waiting for {status}: {latest}")


def test_real_short_child_result_and_whitespace_failure_are_verified(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        handoffs = client.app.state.task_handoffs
        handoffs.plans = _ShortChildPlans("success")
        prepared = _prepare(client)
        started = client.post(
            f"/api/task-handoffs/{prepared['id']}/start",
            headers=HEADERS,
            json={"digest": prepared["digest"], "confirmed": True},
        )
        assert started.status_code == 200
        complete = _wait_for(client, prepared["id"], "completed")
        assert complete["result"]["content"] == "# child result\n"
        handoffs.plans = _ShortChildPlans("whitespace")
        whitespace = _prepare(client)
        client.post(
            f"/api/task-handoffs/{whitespace['id']}/start",
            headers=HEADERS,
            json={"digest": whitespace["digest"], "confirmed": True},
        )
        failed = _wait_for(client, whitespace["id"], "failed")
        assert failed["result"] is None


def test_stop_real_child_is_monotone_and_duplicate_start_dispatches_once(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        handoffs = client.app.state.task_handoffs
        plans = _ShortChildPlans("slow")
        handoffs.plans = plans
        prepared = _prepare(client)
        responses = []
        barrier = threading.Barrier(2)

        def start():
            barrier.wait()
            responses.append(
                client.post(
                    f"/api/task-handoffs/{prepared['id']}/start",
                    headers=HEADERS,
                    json={"digest": prepared["digest"], "confirmed": True},
                ).status_code
            )

        threads = [threading.Thread(target=start) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert responses == [200, 200]
        stopped = client.post(
            f"/api/task-handoffs/{prepared['id']}/stop", headers=HEADERS, json={"confirmed": True}
        )
        assert stopped.status_code == 200
        assert stopped.json()["status"] == "cancelled"
        assert client.get(f"/api/task-handoffs/{prepared['id']}").json()["status"] == "cancelled"
