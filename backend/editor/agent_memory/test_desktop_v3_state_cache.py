"""Cache stavu Desktop v3 podle revize (karta P3, blok 1): zneplatnění po zápisu, obnově verze,
odpojení projektu, izolace projektů a ověření jen změněných uzlů."""
import pytest

from backend.canvas.canvas_service import CanvasService
from backend.editor.agent_memory import desktop_v3_state as module
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State, default_state
from backend.editor.agent_memory.memory_items import MemoryItems
from backend.editor.canvas_versions.canvas_versions import CanvasVersions

NODES = [{"id": "a", "parentId": None, "kind": "node", "name": "A", "purpose": "", "x": 0, "y": 0},
         {"id": "b", "parentId": None, "kind": "node", "name": "B", "purpose": "", "x": 300, "y": 0}]


@pytest.fixture
def service(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    canvas.desktop_v3_state = DesktopV3State(canvas)
    yield canvas
    canvas.close()


def project(service, name="Projekt"):
    pid = service.project_hub.empty_project({"name": name, "confirmed": True})["id"]
    service.save_graph(pid, "draft", {"nodes": NODES, "edges": []}, service.view(pid, "draft")["digest"])
    return pid


def save(store, pid, revision, **nodes):
    state = {**default_state(), "nodes": {key: {"phase": phase, "criteria": [], "steps": []} for key, phase in nodes.items()}}
    return store.save({"project": pid, "workspace": "draft", "expectedRevision": revision, "state": state})


def test_repeated_read_reuses_one_parsed_state_until_a_write(service):
    store, pid = DesktopV3State(service), project(service)
    save(store, pid, 0, a="build")
    first, second = store.read(pid, "draft"), store.read(pid, "draft")
    assert first["state"] is second["state"] and first["revision"] == 1
    save(store, pid, 1, a="define")
    after = store.read(pid, "draft")
    assert after["revision"] == 2 and after["state"]["nodes"]["a"]["phase"] == "define"
    assert after["state"] is not first["state"] and first["state"]["nodes"]["a"]["phase"] == "build"


def test_cache_is_shared_by_every_store_instance_and_isolated_per_project(service):
    one, two = project(service, "Jedna"), project(service, "Dvě")
    save(DesktopV3State(service), one, 0, a="define")
    save(DesktopV3State(service), two, 0, a="verify")
    assert DesktopV3State(service).read(one, "draft")["state"] is DesktopV3State(service).read(one, "draft")["state"]
    assert DesktopV3State(service).read(one, "draft")["state"]["nodes"]["a"]["phase"] == "define"
    assert DesktopV3State(service).read(two, "draft")["state"]["nodes"]["a"]["phase"] == "verify"


def test_restore_of_a_version_invalidates_the_cached_state(service):
    store, pid = DesktopV3State(service), project(service)
    versions = CanvasVersions(service, store)
    save(store, pid, 0, a="build")
    listed = versions.list(pid, "draft")
    saved = versions.save({"project": pid, "workspace": "draft", "digest": service.view(pid, "draft")["digest"],
                           "author": "Test", "expectedToken": listed["currentToken"]})
    save(store, pid, 1, a="build", b="define")
    assert set(store.read(pid, "draft")["state"]["nodes"]) == {"a", "b"}
    token = versions.list(pid, "draft")["currentToken"]
    versions.restore({"project": pid, "workspace": "draft", "versionId": saved["version"]["id"],
                      "digest": service.view(pid, "draft")["digest"], "author": "Test", "expectedToken": token})
    restored = store.read(pid, "draft")
    assert restored["revision"] == 3 and set(restored["state"]["nodes"]) == {"a"}
    assert versions.list(pid, "draft")["currentToken"] != token


def test_removed_project_forgets_its_cached_state(service):
    store, pid = DesktopV3State(service), project(service)
    save(store, pid, 0, a="define")
    store.read(pid, "draft")
    assert ("state", pid, "draft") in service.read_cache._entries
    preview = service.removals.preview(pid, "main", "project", pid)
    service.removals.remove_project({"project": pid, "workspace": "main", "target": pid, "digest": preview["digest"]})
    assert not any(key[1] == pid for key in service.read_cache._entries)


def test_writer_inside_a_transaction_never_fills_the_cache(service):
    store, pid = DesktopV3State(service), project(service)
    save(store, pid, 0, a="define")
    db = service.db_for(pid)
    with service.lock_for(pid), db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE desktop_v3_state SET revision=9, saved_at='uncommitted' WHERE project_id=?", (pid,))
        assert store.current(pid, "draft")["revision"] == 9  # zápis vidí své změny
        db.rollback()
    assert store.read(pid, "draft")["revision"] == 1


def test_shared_cached_state_must_not_be_changed_in_place(service):
    store, pid = DesktopV3State(service), project(service)
    save(store, pid, 0, a="define")
    store.read(pid, "draft")["state"]["nodes"]["a"]["phase"] = "live"
    with pytest.raises(AssertionError, match="změněna na místě"):
        store.read(pid, "draft")


def test_save_with_base_validates_only_changed_nodes(service, monkeypatch):
    store, pid = DesktopV3State(service), project(service)
    save(store, pid, 0, a="build", b="build")
    stored = store.read(pid, "draft")
    seen = []
    original = module._validate_blocks
    monkeypatch.setattr(module, "_validate_blocks", lambda node, node_id: seen.append(node_id) or original(node, node_id))
    state = {**stored["state"], "nodes": {**stored["state"]["nodes"], "b": {"phase": "define", "criteria": [], "steps": []}}}
    saved = store.save({"project": pid, "workspace": "draft", "expectedRevision": 1, "state": state}, base=stored["state"], slim=True)
    assert saved == {"revision": 2, "readOnly": False} and seen == ["b"]
    # Změněný neplatný uzel neprojde ani s `base`; bez `base` se ověří všechny uzly.
    broken = {**state, "nodes": {**state["nodes"], "b": {"phase": "nope", "criteria": [], "steps": []}}}
    with pytest.raises(ValueError, match="fáze uzlu"):
        store.save({"project": pid, "workspace": "draft", "expectedRevision": 2, "state": broken}, base=state)
    seen.clear()
    store.save({"project": pid, "workspace": "draft", "expectedRevision": 2, "state": state})
    assert sorted(seen) == ["a", "b"]


def test_item_write_keeps_unrelated_nodes_shared_and_validates_none_of_them(service, monkeypatch):
    store, pid = DesktopV3State(service), project(service)
    save(store, pid, 0, a="define", b="build")
    seen = []
    original = module._validate_blocks
    monkeypatch.setattr(module, "_validate_blocks", lambda node, node_id: seen.append(node_id) or original(node, node_id))
    decision = {"id": "d", "text": "Rozhodnutí", "nodeId": "", "path": "", "pinned": False,
                "createdAt": "2026-10-10T10:00:00+00:00", "by": "human"}
    result = MemoryItems(store).apply("decisions", {"project": pid, "workspace": "draft", "id": "d", "op": "add",
                                                    "expected": None, "item": decision}, actor="human")
    assert result == {"revision": 2, "readOnly": False, "item": decision} and seen == []
    assert store.read(pid, "draft")["state"]["decisions"] == [decision]


CHILD_WRITE = """
import sys
from backend.canvas.canvas_service import CanvasService
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State, default_state
service = CanvasService(sys.argv[1])
store = DesktopV3State(service)
current = store.read(sys.argv[2], "draft")
state = {**default_state(), "nodes": {"a": {"phase": "verify", "criteria": [], "steps": []}}}
store.save({"project": sys.argv[2], "workspace": "draft", "expectedRevision": current["revision"], "state": state})
service.close()
"""


def test_write_from_another_process_invalidates_cached_state_and_etag(tmp_path):
    """Karta P3 (etapa test): skutečný druhý proces (jiný server nad stejnými daty) zapíše stav;
    první proces nesmí vrátit starý stav z cache ani 304 na starý ETag."""
    import subprocess
    import sys
    from pathlib import Path

    from fastapi.testclient import TestClient

    from backend.app.factory import create_app

    origin = "http://127.0.0.1:8740"
    root = tmp_path / "data"
    with TestClient(create_app(root), base_url=origin) as client:
        pid = client.post("/api/empty-project", headers={"origin": origin}, json={"name": "Sdílený", "confirmed": True}).json()["id"]
        scope = {"project": pid, "workspace": "draft"}
        first = client.get("/api/desktop-v3/state", params=scope)
        assert first.status_code == 200 and first.json()["revision"] == 0
        assert client.get("/api/desktop-v3/state", params=scope, headers={"If-None-Match": first.headers["etag"]}).status_code == 304
        repo = Path(__file__).resolve().parents[3]
        child = subprocess.run([sys.executable, "-c", CHILD_WRITE, str(root), pid], cwd=repo,
                               capture_output=True, text=True, timeout=120, check=False)
        assert child.returncode == 0, child.stderr
        after = client.get("/api/desktop-v3/state", params=scope, headers={"If-None-Match": first.headers["etag"]})
        assert after.status_code == 200 and after.headers["etag"] != first.headers["etag"]
        assert after.json()["revision"] == 1 and after.json()["state"]["nodes"]["a"]["phase"] == "verify"
