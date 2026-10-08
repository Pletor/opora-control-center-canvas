"""Kontrolní pás karty: stejný výpočet pro plátno, frontier i node-brief."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.agent_packet.card_checklist import KEYS, card_items, missing

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
SCOPE = {"project": "draft", "workspace": "draft"}
NODE = {"id": "a", "parentId": None, "kind": "node", "name": "[task] A", "purpose": "", "x": 0, "y": 0}


def block(status, condition=""):
    branch = {"kind": "none", "targetId": "", "note": ""}
    return {"id": "b1", "number": "1", "title": "B", "text": "", "tags": [], "todos": [], "images": [], "parentBlockId": "",
            "state": {"status": status, "condition": condition, "onMet": branch, "onUnmet": branch}}


def states(items):
    return {item["key"]: item["state"] for item in items}


def test_empty_card_misses_everything_but_handoff_without_outgoing_edge():
    items = card_items(NODE, {}, {"goal": "", "non_goals": "", "acceptance": ""}, "", [], {})
    assert [item["key"] for item in items] == list(KEYS)
    assert missing(items) == [key for key in KEYS if key != "handoff"]
    assert all(item["hint"] for item in items if item["state"] == "no")


def test_states_follow_blocks_source_and_handoff_on_edges():
    edges = [{"id": "e1", "source": "a", "target": "z", "port": "next"}, {"id": "e2", "source": "a", "target": "y", "port": "block"}]
    node = {**NODE, "sourceRef": {"origin": "planned", "path": "", "kind": "directory"}}
    items = states(card_items(node, {"blocks": [block("blocked", "Test")]}, {"goal": "Cíl", "non_goals": "", "acceptance": ""},
                              "Výňatek", edges, {"e1": {"handoff": "Pokračuj v z."}}))
    assert items == {"goal": "yes", "done": "yes", "text": "yes", "blocks": "fail", "links": "yes", "source": "run",
                     "checks": "no", "pipeline": "no", "evidence": "no", "handoff": "run"}


def test_route_frontier_and_brief_share_the_checklist(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        view = client.get("/api/view", params=SCOPE).json()
        graph = {"nodes": [NODE, {**NODE, "id": "z", "name": "[task] Z"}], "edges": [{"id": "e1", "source": "a", "target": "z", "port": "next"}]}
        assert client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": graph, "digest": view["digest"]}).status_code == 200
        assert client.post("/api/node-spec", headers=HEADERS, json={**SCOPE, "node": "a", "expected_revision": 0,
                           "fields": {"goal": "Cíl", "non_goals": "", "acceptance": "Projde test"}}).status_code == 200
        layer = client.get("/api/desktop-v3/card-checklist", params=SCOPE).json()["nodes"]
        assert states(layer["a"])["goal"] == "yes" and states(layer["a"])["handoff"] == "no" and states(layer["z"])["goal"] == "no"
        row = client.get("/api/desktop-v3/frontier", params=SCOPE).json()["frontier"][0]
        assert row["id"] == "a" and "goal" not in row["missing"] and "handoff" in row["missing"]
        brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "a"}).json()
        assert states(brief["checklist"]) == states(layer["a"])
