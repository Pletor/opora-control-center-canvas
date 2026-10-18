"""Kontrolní pás karty: stejný výpočet pro plátno, frontier i node-brief."""
import json
import random

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.canvas_service import CanvasService
from backend.editor.agent_packet.card_checklist import KEYS, EdgeIndex, card_items, checklists, missing

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


def test_edge_index_matches_per_card_scans_on_synthetic_edges():
    """Oprava 7: odchozí a dotýkající se vazby z jednoho průchodu = původní filtry přes všechny vazby."""
    rnd = random.Random(7)
    ids = [f"k{i}" for i in range(30)]
    edges = [{"id": f"e{i}", "source": rnd.choice(ids), "target": rnd.choice(ids), **({"port": p} if (p := rnd.choice(["next", "block", "sub", None])) else {})}
             for i in range(90)]
    index = EdgeIndex(edges)
    for node_id in ids + ["nikde"]:
        assert index.outgoing.get(node_id, []) == [e for e in edges if e["source"] == node_id and e.get("port", "next") in ("next", "block")]
        assert index.touching.get(node_id, []) == [e for e in edges if node_id in (e["source"], e["target"])]
        node = {**NODE, "id": node_id}
        reports = {e["id"]: {"handoff": "ok"} for e in edges[::3]}
        assert card_items(node, {}, {"goal": ""}, "", edges, reports) == card_items(node, {}, {"goal": ""}, "", index, reports)


def test_bulk_checklists_match_per_card_reads(tmp_path):
    """Hromadné čtení zadání a textů (poslední revize, jen tento prostor) = původní dva dotazy na kartu."""
    service = CanvasService(tmp_path / "data")
    service.view("draft", "draft")
    nodes = [{**NODE, "id": f"k{i}", "kind": "sector" if i % 5 == 0 else "node"} for i in range(8)] + [{**NODE, "id": "c", "kind": "comment"}]
    graph = {"nodes": nodes, "edges": [{"id": "e1", "source": "k1", "target": "k2", "port": "next"}]}
    db = service.db_for("draft")
    with db:
        for rev, goal in ((1, "starý"), (2, "nový"), (3, "")):
            db.execute("INSERT INTO node_spec_revisions VALUES(?,?,?,?,?,?)", ("draft", "draft", "k1", rev, json.dumps({"goal": goal, "non_goals": "", "acceptance": "x"}), "t"))
        db.execute("INSERT INTO node_spec_revisions VALUES(?,?,?,?,?,?)", ("draft", "draft", "k2", 1, json.dumps({"goal": "Cíl", "non_goals": "", "acceptance": ""}), "t"))
        db.execute("INSERT INTO node_spec_revisions VALUES(?,?,?,?,?,?)", ("draft", "jiny", "k3", 1, json.dumps({"goal": "Cizí", "non_goals": "", "acceptance": ""}), "t"))
        for rev, text in ((1, "první"), (2, "")):
            db.execute("INSERT INTO node_text_revisions VALUES(?,?,?,?,?,?)", ("draft", "draft", "k2", rev, text, "t"))
        db.execute("INSERT INTO node_text_revisions VALUES(?,?,?,?,?,?)", ("draft", "draft", "k4", 1, "Výňatek", "t"))
        db.execute("INSERT INTO node_text_revisions VALUES(?,?,?,?,?,?)", ("draft", "jiny", "k5", 1, "Cizí", "t"))
    state = {"nodes": {"k1": {"blocks": [block("met", "Podmínka")]}}, "edges": {"e1": {"handoff": "Dál"}}}

    def reference(node_ids=None):
        out = {}
        for node in graph["nodes"]:
            if node.get("kind") not in ("node", "sector") or (node_ids is not None and node["id"] not in node_ids):
                continue
            scope = ("draft", "draft", node["id"])
            out[node["id"]] = card_items(node, state["nodes"].get(node["id"], {}), service.specs.read(scope)["fields"],
                                         service.texts.read(scope)["text"], graph["edges"], state["edges"])
        return out

    for node_ids in (None, set(), {"k1", "k4", "c", "nikde"}):
        assert json.dumps(checklists(service, "draft", "draft", graph, state, node_ids), ensure_ascii=False) == json.dumps(reference(node_ids), ensure_ascii=False)
    assert states(checklists(service, "draft", "draft", graph, state)["k4"])["text"] == "yes"
    service.close()
