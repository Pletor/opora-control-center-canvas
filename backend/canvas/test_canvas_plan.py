"""Dávka plánu `/api/canvas-plan` (docs/davka-planu.md §3 a §5): projde celá, nebo nic."""
import copy

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.areas import area_of
from backend.canvas.canvas_plan import apply_plan
from backend.canvas.canvas_plan_summary import plan_summary
from backend.canvas.canvas_service import CanvasService
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.canvas.canvas_plan_layout import overlapping

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}
SCOPE = {"project": "draft", "workspace": "draft"}
NONE = {"kind": "none", "targetId": "", "note": ""}

GRAPH = {
    "nodes": [
        {"id": "s0", "parentId": None, "kind": "sector", "name": "Starý sektor", "purpose": "", "x": 0, "y": 0},
        {"id": "n0", "parentId": "s0", "kind": "node", "name": "Stará karta", "purpose": "", "x": 0, "y": 0},
        {"id": "a0", "parentId": None, "kind": "area", "name": "Stará oblast", "purpose": "",
         "x": 500, "y": 0, "size": {"w": 600, "h": 400}},
    ],
    "edges": [],
}
STATE = {
    "settings": [], "rules": [], "decisions": [], "tickets": [], "edges": {},
    "nodes": {"n0": {"phase": "discover", "criteria": [], "steps": [], "blocks": [{
        "id": "b0", "number": "1", "title": "Starý blok", "text": "", "tags": [], "todos": [], "images": [],
        "state": {"status": "open", "condition": "", "onMet": NONE, "onUnmet": NONE},
        "parentBlockId": "", "ports": [{"id": "p0", "label": "Hotovo"}],
    }]}},
}


def plan():
    return {
        "nodes": [
            {"ref": "pilot", "kind": "area", "parent": None, "name": "Pilot", "size": {"w": 1400, "h": 900},
             "text": "Celé zadání Jihlavy."},
            {"ref": "vlna", "kind": "sector", "parent": "pilot", "name": "Vlna 2", "purpose": "Zpracování dokumentů",
             "sourceRef": {"origin": "planned", "path": "api", "kind": "directory"}},
            {"ref": "vzorek", "kind": "node", "parent": "vlna", "name": "[task] Vzorek dat"},
            {"ref": "ingest", "kind": "node", "parent": "vlna", "name": "[task] Pipeline zpracování",
             "purpose": "Dokument projde od nahrání po chunk.",
             "sourceRef": {"origin": "planned", "path": "api/ingest", "kind": "directory"},
             "spec": {"goal": "Dokumenty se zpracují.", "non_goals": "Chunking řeší karta Chunking.",
                      "acceptance": "uv run pytest api"},
             "text": "Zadání Jihlava, kap. Zpracování dat, kroky 1–9.",
             "agentRole": "role-backend",
             "blocks": [
                 {"ref": "formaty", "title": "Formáty vstupu", "text": "PDF, DOCX, XLSX",
                  "condition": "Každý povinný formát projde.",
                  "ports": [{"ref": "ok", "label": "Splněno → chunking"}, {"ref": "ocr", "label": "Sken → OCR"}]},
                 {"ref": "meta", "title": "Metadata"},
             ],
             "rules": [{"kind": "must", "text": "Každý záznam nese organizaci a projekt."},
                       {"kind": "must_not", "text": "Neodpovídat z obecných znalostí."}]},
            {"ref": "chunking", "kind": "node", "parent": "vlna", "name": "[task] Chunking"},
            {"ref": "druha", "kind": "area", "parent": None, "name": "Widget", "size": {"w": 600, "h": 400}},
            {"ref": "lisek", "kind": "comment", "parent": None, "name": "Poznámka", "purpose": "Jen pro lidi."},
        ],
        "edges": [
            {"from": "vzorek", "to": "ingest", "port": "next"},
            {"from": "ingest", "to": "chunking", "port": "block", "block": "formaty", "blockPort": "ok"},
            {"from": "@n0", "to": "ingest", "port": "block", "block": "b0", "blockPort": "p0"},
            {"from": "@a0", "to": "pilot", "port": "flow"},
            {"from": "pilot", "to": "druha", "port": "flow"},
            {"from": "ingest", "to": "@n0", "port": "rule"},
        ],
        "decisions": [{"node": "ingest", "text": "Extrakce: docling-serve + Tesseract cs.", "pinned": False}],
    }


def seed(client):
    view = client.get("/api/view", params=SCOPE).json()
    saved = client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": GRAPH, "digest": view["digest"]})
    assert saved.status_code == 200, saved.text
    state = client.post("/api/desktop-v3/state", headers=HEADERS,
                        json={**SCOPE, "expectedRevision": 0, "state": STATE})
    assert state.status_code == 200, state.text
    return saved.json()["digest"]


def send(client, digest, body, dry=False):
    return client.post("/api/canvas-plan", headers=HEADERS,
                       json={**SCOPE, "digest": digest, "dryRun": dry, "plan": body})


def snapshot(client, node_ids=()):
    return {
        "view": client.get("/api/view", params=SCOPE).json()["digest"],
        "state": client.get("/api/desktop-v3/state", params=SCOPE).json()["revision"],
        "texts": [client.get("/api/node-text", params={**SCOPE, "node": n}).json()["revision"] for n in node_ids],
    }


def test_full_plan_lands_and_node_brief_reads_it(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        digest = seed(client)
        response = send(client, digest, plan())
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["ok"] is True and body["dryRun"] is False
        assert body["summary"] == (
            "Přidá 2 oblasti, 1 sektor, 3 karty, 1 komentář, 2 bloky, 2 porty, "
            "6 vazeb (next 1, rule 1, block 2, flow 2), 2 pravidla, 1 rozhodnutí, text u 2 karet."
        )
        # Souhrn se počítá z nepřeloženého plánu; tentýž text dá i log aktivit.
        assert plan_summary(plan()) == body["summary"]
        refs, ingest = body["refs"], body["refs"]["ingest"]
        assert set(body["blocks"]) == {"ingest/formaty", "ingest/meta"}
        assert body["revision"] == 2

        graph = client.get("/api/view", params=SCOPE).json()
        assert graph["digest"] == body["digest"]
        nodes = graph["graph"]["nodes"]
        by_id = {node["id"]: node for node in nodes}
        # Existující uzly zůstaly beze změny, nové stojí bez překryvu.
        assert [by_id[n["id"]] for n in GRAPH["nodes"]] == GRAPH["nodes"]
        assert overlapping(nodes) == []
        # Sektor „v oblasti“ leží na vrstvě oblasti a geometricky do ní patří.
        assert by_id[refs["vlna"]]["parentId"] is None
        assert area_of(by_id[refs["vlna"]], nodes)["id"] == refs["pilot"]
        assert area_of(by_id[refs["lisek"]], nodes) is None

        brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": ingest})
        assert brief.status_code == 200, brief.text
        brief = brief.json()
        assert brief["goal"]["goal"] == "Dokumenty se zpracují."
        assert brief["content"] == {"text": "Zadání Jihlava, kap. Zpracování dat, kroky 1–9.", "revision": 1}
        blocks = brief["blocks"]
        assert [b["title"] for b in blocks] == ["Formáty vstupu", "Metadata"]
        assert blocks[0]["state"]["condition"] == "Každý povinný formát projde."
        ports = {p["id"]: p for p in blocks[0]["ports"]}
        assert ports["ok"]["label"] == "Splněno → chunking"
        assert [e["targetId"] for e in ports["ok"]["edges"]] == [refs["chunking"]]
        assert {r["text"] for r in brief["boundaries"]["projectRules"]} == {
            "Každý záznam nese organizaci a projekt.", "Neodpovídat z obecných znalostí."}
        assert [d["text"] for d in brief["context"]["decisions"]] == ["Extrakce: docling-serve + Tesseract cs."]
        state = client.get("/api/desktop-v3/state", params=SCOPE).json()["state"]
        assert state["nodes"][ingest]["agentRole"] == "role-backend"
        assert state["nodes"]["n0"] == STATE["nodes"]["n0"]
        incoming = {(e["from"], e["port"]) for e in brief["graph"]["incoming"]}
        assert {(refs["vzorek"], "next"), ("n0", "block")} <= incoming

        text = client.get("/api/node-text", params={**SCOPE, "node": ingest}).json()
        assert (text["revision"], text["text"]) == (1, "Zadání Jihlava, kap. Zpracování dat, kroky 1–9.")
        spec = client.get("/api/node-spec", params={**SCOPE, "node": ingest}).json()
        assert spec["revision"] == 1


def test_dry_run_previews_and_writes_nothing(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        digest = seed(client)
        before = snapshot(client)
        response = send(client, digest, plan(), dry=True)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["dryRun"] is True and set(body["refs"]) == {n["ref"] for n in plan()["nodes"]}
        assert body["summary"].startswith("Přidá 2 oblasti")
        assert body["digest"] == digest and body["revision"] == 1
        assert snapshot(client) == before


def broken(mutate):
    body = plan()
    mutate(body)
    return body


def test_bad_item_writes_nothing_and_names_it(tmp_path):
    cases = [
        (broken(lambda p: p["nodes"][3]["blocks"][0]["ports"].extend(
            {"ref": f"x{i}", "label": ""} for i in range(7))), "ingest/formaty"),
        (broken(lambda p: p["edges"].append({"from": "lisek", "to": "ingest"})), "edges[6]"),
        (broken(lambda p: p["edges"].append({"from": "nikdo", "to": "ingest"})), "neznámý ref"),
        (broken(lambda p: p["edges"].append(
            {"from": "ingest", "to": "chunking", "port": "block", "block": "formaty", "blockPort": "zadny"})),
         "nemá port"),
        (broken(lambda p: p["nodes"][3].update(spec={"goal": "x" * 5000})), "ingest"),
        (broken(lambda p: p["nodes"][3].update(agentRole="neznama")), "role karty ingest"),
    ]
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        digest = seed(client)
        before = snapshot(client)
        for body, needle in cases:
            response = send(client, digest, body)
            assert response.status_code == 409, response.text
            assert needle in response.json()["error"]
            assert snapshot(client) == before
        stale = send(client, "0" * 64, plan())
        assert stale.status_code == 409 and "změnilo" in stale.json()["error"]
        assert snapshot(client) == before


def test_failing_graph_write_rolls_back_state_spec_and_text(tmp_path, monkeypatch):
    service = CanvasService(tmp_path / "data")
    store = DesktopV3State(service)
    service.desktop_v3_state = store
    digest = service.save_graph("draft", "draft", GRAPH, service.view("draft", "draft")["digest"])["digest"]
    store.save({**SCOPE, "expectedRevision": 0, "state": STATE})

    def boom(*args, **kwargs):
        raise OSError("disk plný")

    monkeypatch.setattr(service, "save_graph", boom)
    with pytest.raises(OSError):
        apply_plan(service, {**SCOPE, "digest": digest, "plan": plan()})
    stored = store.read("draft", "draft")
    assert stored["revision"] == 1 and set(stored["state"]["nodes"]) == {"n0"}
    db = service.db_for("draft")
    assert db.execute("SELECT COUNT(*) FROM node_text_revisions").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM node_spec_revisions").fetchone()[0] == 0
    assert service.view("draft", "draft")["digest"] == digest
    service.close()


def test_full_area_grows_to_take_more_cards(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        digest = seed(client)
        body = {"nodes": [{"ref": f"k{i}", "kind": "node", "parent": "@a0", "name": f"Karta {i}"} for i in range(3)]}
        response = send(client, digest, copy.deepcopy(body))
        assert response.status_code == 200, response.text
        nodes = {n["id"]: n for n in client.get("/api/view", params=SCOPE).json()["graph"]["nodes"]}
        area = nodes["a0"]
        # 600 × 400 bere jednu kartu; pro tři vyroste do šířky na tři sloupce, výška stačí.
        assert area["size"] == {"w": 2 * 48 + 3 * 360 + 2 * 96, "h": 400}
        for ref in ("k0", "k1", "k2"):
            card = nodes[response.json()["refs"][ref]]
            assert card["parentId"] is None
            assert area["x"] <= card["x"] and card["x"] + 360 <= area["x"] + area["size"]["w"]
            assert area["y"] <= card["y"] and card["y"] + 240 <= area["y"] + area["size"]["h"]


def test_card_inside_hemmed_in_area_is_an_error(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        digest = seed(client)
        # Sousedi těsně vpravo a dole: oblast 600 × 400 nemá kam vyrůst.
        fence = {"nodes": [
            {"ref": "vpravo", "kind": "sector", "parent": None, "name": "Vpravo", "purpose": "Plot vpravo od oblasti.",
             "position": {"x": 500 + 600 + 96, "y": 0}},
            {"ref": "dole", "kind": "sector", "parent": None, "name": "Dole", "purpose": "Plot pod oblastí.",
             "position": {"x": 500, "y": 400 + 96}},
        ]}
        fenced = send(client, digest, fence)
        assert fenced.status_code == 200, fenced.text
        body = {"nodes": [{"ref": f"k{i}", "kind": "node", "parent": "@a0", "name": f"Karta {i}"} for i in range(2)]}
        response = send(client, fenced.json()["digest"], copy.deepcopy(body))
        assert response.status_code == 409
        assert "k1: karta se nevejde do oblasti" in response.json()["error"]
