"""Strom obsahu uzlu: očíslované bloky, štítky, TODO, obrázky jako reference, stav s větvením."""
import copy

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.agent_memory.desktop_v3_state import validate_state

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
SCOPE = {"project": "draft", "workspace": "draft"}
EMPTY = {"settings": [], "rules": [], "decisions": [], "nodes": {}, "tickets": []}


def branch(kind="none", target="", note=""):
    return {"kind": kind, "targetId": target, "note": note}


def block(bid, number, parent="", **overrides):
    item = {
        "id": bid, "number": number, "title": f"Blok {number}", "text": "", "tags": [], "todos": [], "images": [],
        "state": {"status": "open", "condition": "", "onMet": branch(), "onUnmet": branch()},
        "parentBlockId": parent,
    }
    item.update(overrides)
    return item


def node(blocks):
    return {"phase": "discover", "criteria": [], "steps": [], "blocks": blocks}


def state(blocks):
    value = copy.deepcopy(EMPTY)
    value["nodes"] = {"focus": node(blocks)}
    return value


def test_blocks_with_tags_todos_images_and_state_are_accepted():
    blocks = [
        block("b1", "1", tags=["auth", "kritické"],
              todos=[{"id": "t1", "text": "Napsat test", "done": False, "assignee": ""}],
              images=[{"id": "i1", "path": "docs/mockups/login.png", "caption": "Inspirace"}],
              state={"status": "open", "condition": "Testy zelené",
                     "onMet": branch("block", "b2", "pokračuj"), "onUnmet": branch("none")}),
        block("b2", "1.1", parent="b1"),
    ]
    assert validate_state(state(blocks))["nodes"]["focus"]["blocks"] == blocks


def test_node_without_blocks_and_legacy_node_stay_valid():
    legacy = {"phase": "discover", "criteria": [], "steps": []}
    value = copy.deepcopy(EMPTY)
    value["nodes"] = {"focus": legacy}
    assert validate_state(value)["nodes"]["focus"] == legacy


@pytest.mark.parametrize(
    "blocks",
    [
        [block("b1", "1", parent="b1")],
        [block("b1", "1", parent="missing")],
        [block("b1", "1"), block("b2", "1")],
        [block("b1", "one")],
        [block("b1", "1", tags=["x" * 41])],
        [block("b1", "1", tags=[""])],
        [block("b1", "1", todos=[{"id": "t1", "text": "", "done": False, "assignee": ""}])],
        [block("b1", "1", images=[{"id": "i1", "path": "../secret.png", "caption": ""}])],
        [block("b1", "1", images=[{"id": "i1", "path": "", "caption": ""}])],
        [block("b1", "1", state={"status": "done", "condition": "", "onMet": branch(), "onUnmet": branch()})],
        [block("b1", "1", state={"status": "open", "condition": "", "onMet": branch("block", "nope"), "onUnmet": branch()})],
        [block("b1", "1", state={"status": "open", "condition": "", "onMet": branch("none", "b1"), "onUnmet": branch()})],
        [block("b1", "1", state={"status": "open", "condition": "", "onMet": branch("teleport", "b1"), "onUnmet": branch()})],
        [block("b1", "1", parent="b2"), block("b2", "2", parent="b1")],
    ],
)
def test_invalid_blocks_are_rejected(blocks):
    with pytest.raises(ValueError):
        validate_state(state(blocks))


def _seed_graph(client):
    view = client.get("/api/view", params=SCOPE).json()
    graph = {
        "nodes": [
            {"id": "focus", "parentId": None, "kind": "node", "name": "Ohnisko", "purpose": "", "x": 0, "y": 0},
            {"id": "menu", "parentId": None, "kind": "node", "name": "Menu", "purpose": "", "x": 300, "y": 0},
        ],
        "edges": [],
    }
    assert client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": graph, "digest": view["digest"]}).status_code == 200


def _post(client, value, expected=0):
    return client.post("/api/desktop-v3/state", headers=HEADERS, json={**SCOPE, "expectedRevision": expected, "state": value})


def test_branch_to_node_or_action_is_checked_against_graph_and_actions_on_save(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        _seed_graph(client)
        ok = state([block("b1", "1", state={"status": "met", "condition": "", "onMet": branch("node", "menu"), "onUnmet": branch()})])
        ok["nodes"]["focus"]["actions"] = [{"id": "a1", "pipelineId": "verify.run-tests", "label": "Testy", "params": {}}]
        ok["nodes"]["focus"]["rules"] = []
        ok["nodes"]["focus"]["blocks"][0]["state"]["onUnmet"] = branch("action", "a1")
        assert _post(client, ok).status_code == 200
        bad = copy.deepcopy(ok)
        bad["nodes"]["focus"]["blocks"][0]["state"]["onMet"] = branch("node", "ghost")
        response = _post(client, bad, expected=1)
        assert response.status_code == 409 and "ghost" in response.json()["error"]
        bad["nodes"]["focus"]["blocks"][0]["state"]["onMet"] = branch("action", "a9")
        assert _post(client, bad, expected=1).status_code == 409
