"""Štíhlý zápis jedné karty (`DesktopV3State.save_node`, oprava 8 v docs/navrhy/2026-10-14-vykon-platna.md).

Tělo i odpověď nesou jen jeden uzel; revize se hlídá stejně jako u celého zápisu, pravidla uložení
platí beze změny a ostatní karty zůstávají sdílené s uloženým stavem (znovu se neověřují).
"""
import json

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.activity_log import HumanRequired
from backend.canvas.canvas_service import CanvasService, now
from backend.editor.agent_memory import desktop_v3_state as module
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State, default_state
from backend.editor.agent_memory.test_desktop_v3_state_cache import project, save
from backend.editor.node.test_removals import state_block

ORIGIN = "http://127.0.0.1:8740"
SCOPE = {"project": "draft", "workspace": "draft"}


@pytest.fixture
def service(tmp_path):
    canvas = CanvasService(tmp_path / "data")
    canvas.desktop_v3_state = DesktopV3State(canvas)
    yield canvas
    canvas.close()


def patch(store, pid, revision, node_id, node, actor="human"):
    return store.save_node({"project": pid, "workspace": "draft", "expectedRevision": revision,
                            "nodeId": node_id, "node": node}, actor=actor)


def card(phase="discover", **extra):
    return {"phase": phase, "criteria": [], "steps": [], **extra}


def test_patch_writes_one_node_answers_slim_and_keeps_other_nodes_shared(service, monkeypatch):
    store, pid = DesktopV3State(service), project(service)
    save(store, pid, 0, a="define", b="build")
    before = store.read(pid, "draft")["state"]
    seen = []
    original = module._validate_blocks
    monkeypatch.setattr(module, "_validate_blocks", lambda node, node_id: seen.append(node_id) or original(node, node_id))
    node = card("define", blocks=[state_block()])
    saved = patch(store, pid, 1, "a", node)
    assert saved == {"revision": 2, "readOnly": False, "nodeId": "a", "node": node} and seen == ["a"]
    after = store.read(pid, "draft")
    assert after["revision"] == 2 and after["state"]["nodes"]["a"] == node
    assert after["state"]["nodes"]["b"] == before["nodes"]["b"]
    assert {k: v for k, v in after["state"].items() if k != "nodes"} == {k: v for k, v in before.items() if k != "nodes"}


def test_stale_revision_is_a_conflict_and_nothing_is_written(service):
    store, pid = DesktopV3State(service), project(service)
    save(store, pid, 0, a="define")
    patch(store, pid, 1, "a", card("discover"))
    with pytest.raises(ValueError, match="revize nesouhlasí"):
        patch(store, pid, 1, "a", card("define"))
    assert store.read(pid, "draft")["revision"] == 2
    assert store.read(pid, "draft")["state"]["nodes"]["a"]["phase"] == "discover"


def test_new_node_state_needs_a_graph_card_and_null_removes_existing_state(service):
    store, pid = DesktopV3State(service), project(service)
    assert patch(store, pid, 0, "b", card())["revision"] == 1  # karta v grafu, stav ještě neměla
    with pytest.raises(ValueError, match="neexistuje"):
        patch(store, pid, 1, "ghost", card())
    assert patch(store, pid, 1, "b", None) == {"revision": 2, "readOnly": False, "nodeId": "b", "node": None}
    assert store.read(pid, "draft")["state"]["nodes"] == {}
    with pytest.raises(ValueError, match="není co odebrat"):
        patch(store, pid, 2, "b", None)


@pytest.mark.parametrize("payload, message", [
    ({"nodeId": "a", "node": card()}, "vyžaduje"),
    ({**SCOPE, "expectedRevision": 0, "nodeId": "a", "node": card(), "state": {}}, "vyžaduje"),
    ({**SCOPE, "expectedRevision": 0, "nodeId": "../a", "node": card()}, "identifikátor"),
    ({**SCOPE, "expectedRevision": 0, "nodeId": "a", "node": []}, "objekt"),
    ({**SCOPE, "expectedRevision": 0, "nodeId": "a", "node": card("nope")}, "fáze uzlu"),
    ({**SCOPE, "expectedRevision": 0, "nodeId": "a", "node": {**card(), "extra": 1}}, "neplatná pole"),
])
def test_invalid_payload_is_rejected(service, payload, message):
    store, pid = DesktopV3State(service), project(service)
    if "project" in payload:
        payload = {**payload, "project": pid}
    with pytest.raises(ValueError, match=message):
        store.save_node(payload, actor="human")


def test_save_rules_still_apply_to_the_patched_node(service):
    store, pid = DesktopV3State(service), project(service)
    save(store, pid, 0, a="discover")
    done = {"confirmed": True, "at": now(), "by": "human", "note": ""}
    with pytest.raises(HumanRequired):
        patch(store, pid, 1, "a", card(done=done), actor="agent")
    # Uzavřená karta (zapsaná přímo, bez důkazů) má bloky jen ke čtení i ve štíhlém zápisu.
    closed = {**default_state(), "nodes": {"a": card(done=done, blocks=[state_block()])}}
    with service.lock_for(pid), service.db_for(pid) as db:
        db.execute("INSERT OR REPLACE INTO desktop_v3_state VALUES(?,?,?,?,?)",
                   (pid, "draft", 5, json.dumps(closed), now()))
    with pytest.raises(ValueError, match="jen ke čtení"):
        patch(store, pid, 5, "a", card(done=done, blocks=[{**state_block(), "text": "změna"}]))


def test_route_writes_a_node_of_a_state_too_big_for_a_full_write(tmp_path):
    """1600 karet po 3 blocích: celý stav (> 2 MB) dostane 413, štíhlý zápis karty projde v kB."""
    nodes = [{"id": f"n{i}", "parentId": None, "kind": "node", "name": f"Karta {i}", "purpose": "", "x": i, "y": 0}
             for i in range(1600)]
    blocks = [{**state_block(f"b{b}", str(b + 1)), "text": "Text bloku " * 30} for b in range(3)]
    state = {**default_state(), "nodes": {n["id"]: card(blocks=blocks) for n in nodes}}
    canvas = CanvasService(tmp_path / "data")
    try:
        canvas.save_graph("draft", "draft", {"nodes": nodes, "edges": []}, canvas.view("draft", "draft")["digest"])
        DesktopV3State(canvas).save({**SCOPE, "expectedRevision": 0, "state": state})
    finally:
        canvas.close()
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        stored = client.get("/api/desktop-v3/state", params=SCOPE).json()
        full = client.post("/api/desktop-v3/state", headers={"origin": ORIGIN},
                           json={**SCOPE, "expectedRevision": stored["revision"], "state": stored["state"]})
        assert full.status_code == 413
        node = card(blocks=[{**blocks[0], "text": "Upraveno"}, *blocks[1:]])
        body = {**SCOPE, "expectedRevision": stored["revision"], "nodeId": "n7", "node": node}
        response = client.post("/api/desktop-v3/node", headers={"origin": ORIGIN}, json=body)
        assert response.status_code == 200, response.text
        assert response.json() == {"revision": 2, "readOnly": False, "nodeId": "n7", "node": node}
        assert len(response.content) < 5000
        again = client.post("/api/desktop-v3/node", headers={"origin": ORIGIN}, json=body)
        assert again.status_code == 409 and "revize" in again.json()["error"]
        after = client.get("/api/desktop-v3/state", params=SCOPE).json()
        assert after["revision"] == 2 and after["state"]["nodes"]["n7"]["blocks"][0]["text"] == "Upraveno"
