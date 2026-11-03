import copy

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.canvas_plan import apply_plan
from backend.canvas.canvas_service import CanvasService
from backend.canvas.test_canvas_plan import (
    GRAPH,
    ORIGIN,
    SCOPE,
    STATE,
    seed,
    send,
    snapshot,
)
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State


def extension(client):
    return {"node": "@n0", "expectedRevision": client.get("/api/desktop-v3/state", params=SCOPE).json()["revision"],
            "blocks": [{"ref": "new-block", "title": "New block", "ports": [{"ref": "yes", "label": "Continue"}]}],
            "ports": [{"block": "b0", "ports": [{"ref": "extra", "label": "Extra"}]}],
            "rules": [{"kind": "must", "text": "Keep history"}],
            "spec": {"expectedRevision": 0, "fields": {"goal": "Extended"}},
            "text": {"expectedRevision": 0, "text": "Extended instructions"}}


def test_extend_all_content_dry_run_commit_and_revision_conflict(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        digest = seed(client)
        body = {"extend": [extension(client)], "edges": [{"from": "@n0", "to": "@s0", "port": "block", "block": "new-block", "blockPort": "yes"}]}
        before = snapshot(client, ["n0"])
        dry = send(client, digest, body, dry=True)
        assert dry.status_code == 200, dry.text
        assert snapshot(client, ["n0"]) == before
        result = send(client, digest, body)
        assert result.status_code == 200, result.text
        assert "Rozšíří 1" in result.json()["summary"]
        entries = client.get("/api/activity-log", params={**SCOPE, "nodeId": "n0"}).json()["entries"]
        assert any(entry["status"] == 200 and "Rozšíří 1" in entry["summary"] for entry in entries)
        stored = client.get("/api/desktop-v3/state", params=SCOPE).json()
        blocks = stored["state"]["nodes"]["n0"]["blocks"]
        assert [b["number"] for b in blocks] == ["1", "2"]
        assert [p["id"] for p in blocks[0]["ports"]] == ["p0", "extra"]
        assert blocks[1]["id"] == result.json()["blocks"]["@n0/new-block"]
        assert stored["state"]["rules"][0]["target"] == "n0"
        assert client.get("/api/node-spec", params={**SCOPE, "node": "n0"}).json()["fields"]["goal"] == "Extended"
        after = snapshot(client, ["n0"])
        assert send(client, result.json()["digest"], body).status_code == 409
        assert snapshot(client, ["n0"]) == after
        body2 = {"extend": [{"node": "@n0", "expectedRevision": stored["revision"], "spec": {"expectedRevision": 1, "fields": {"acceptance": "Pass"}}, "text": {"expectedRevision": 1, "text": "New revision"}}]}
        assert send(client, result.json()["digest"], body2).status_code == 200
        fields = client.get("/api/node-spec", params={**SCOPE, "node": "n0"}).json()["fields"]
        assert fields["goal"] == "Extended" and fields["acceptance"] == "Pass"
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        assert client.get("/api/node-text", params={**SCOPE, "node": "n0"}).json()["text"] == "New revision"


def test_bad_port_or_stale_text_rolls_back_entire_extension(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        digest = seed(client)
        item = extension(client)
        before = snapshot(client, ["n0"])
        duplicate = copy.deepcopy(item)
        duplicate["ports"][0]["ports"][0]["ref"] = "p0"
        stale = copy.deepcopy(item)
        stale["text"]["expectedRevision"] = 1
        for bad in (duplicate, stale):
            assert send(client, digest, {"extend": [bad]}).status_code == 409
            assert snapshot(client, ["n0"]) == before


def test_failed_graph_write_rolls_back_existing_documents_and_state(tmp_path, monkeypatch):
    service = CanvasService(tmp_path)
    store = DesktopV3State(service)
    service.desktop_v3_state = store
    try:
        digest = service.save_graph("draft", "draft", GRAPH, service.view("draft", "draft")["digest"])["digest"]
        store.save({**SCOPE, "expectedRevision": 0, "state": STATE})
        original = store.read("draft", "draft")
        def fail(*args, **kwargs):
            raise OSError("disk full")
        monkeypatch.setattr(service, "save_graph", fail)
        with pytest.raises(OSError):
            apply_plan(service, {**SCOPE, "digest": digest, "plan": {"extend": [{"node": "@n0", "expectedRevision": 1,
                "blocks": [{"ref": "new", "title": "New"}], "spec": {"expectedRevision": 0, "fields": {"goal": "New"}},
                "text": {"expectedRevision": 0, "text": "New"}}]}})
        assert store.read("draft", "draft") == original
        assert service.db_for("draft").execute("SELECT COUNT(*) FROM node_spec_revisions").fetchone()[0] == 0
        assert service.db_for("draft").execute("SELECT COUNT(*) FROM node_text_revisions").fetchone()[0] == 0
    finally:
        service.close()


def test_replace_blocks_swaps_card_blocks_unless_a_block_edge_starts_there(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        digest = seed(client)
        revision = client.get("/api/desktop-v3/state", params=SCOPE).json()["revision"]
        bad = {"node": "@n0", "expectedRevision": revision, "replaceBlocks": True, "spec": {"expectedRevision": 0, "fields": {}}}
        assert send(client, digest, {"extend": [bad]}).status_code == 409  # replaceBlocks bez blocks
        item = {"node": "@n0", "expectedRevision": revision, "replaceBlocks": True,
                "blocks": [{"ref": "a", "title": "A"}, {"ref": "b", "title": "B", "condition": "hotovo"}]}
        result = send(client, digest, {"extend": [item]})
        assert result.status_code == 200, result.text
        assert "Bloky nahradí u 1" in result.json()["summary"]
        blocks = client.get("/api/desktop-v3/state", params=SCOPE).json()["state"]["nodes"]["n0"]["blocks"]
        assert [(b["number"], b["title"]) for b in blocks] == [("1", "A"), ("2", "B")]
        assert blocks[1]["state"]["condition"] == "hotovo"
        # Vazba z bloku karty: nahrazení by ji nechalo viset, proto 409 a nic se nezapíše.
        linked = {"extend": [{**extension(client), "spec": {"expectedRevision": 0, "fields": {"goal": "x"}}}],
                  "edges": [{"from": "@n0", "to": "@s0", "port": "block", "block": "new-block", "blockPort": "yes"}]}
        linked["extend"][0].pop("ports")
        done = send(client, result.json()["digest"], linked)
        assert done.status_code == 200, done.text
        again = {"node": "@n0", "expectedRevision": client.get("/api/desktop-v3/state", params=SCOPE).json()["revision"],
                 "replaceBlocks": True, "blocks": [{"ref": "c", "title": "C"}]}
        before = snapshot(client, ["n0"])
        refused = send(client, done.json()["digest"], {"extend": [again]})
        assert refused.status_code == 409 and "vazba" in refused.json()["error"]
        assert snapshot(client, ["n0"]) == before


def test_extend_layer_changes_card_layer_and_keeps_it_without_layer(tmp_path):
    def layer_of(client):
        nodes = client.get("/api/view", params=SCOPE).json()["graph"]["nodes"]
        return next(n for n in nodes if n["id"] == "n0").get("card", {}).get("layer")

    def revision(client):
        return client.get("/api/desktop-v3/state", params=SCOPE).json()["revision"]

    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        digest = seed(client)
        blocks = [{"ref": "a", "title": "A"}]
        first = {"node": "@n0", "expectedRevision": revision(client), "blocks": blocks, "replaceBlocks": True, "layer": "frontend"}
        result = send(client, digest, {"extend": [first]})
        assert result.status_code == 200, result.text
        assert layer_of(client) == "frontend"
        second = {"node": "@n0", "expectedRevision": revision(client), "blocks": blocks, "replaceBlocks": True, "layer": "backend"}
        stale = send(client, result.json()["digest"], {"extend": [{**second, "expectedRevision": 0}]})
        assert stale.status_code == 409 and layer_of(client) == "frontend"
        bad = send(client, result.json()["digest"], {"extend": [{**second, "layer": "nonsense"}]})
        assert bad.status_code == 409 and layer_of(client) == "frontend"
        changed = send(client, result.json()["digest"], {"extend": [second]})
        assert changed.status_code == 200, changed.text
        assert layer_of(client) == "backend"
        keep = {"node": "@n0", "expectedRevision": revision(client), "blocks": blocks, "replaceBlocks": True}
        assert send(client, changed.json()["digest"], {"extend": [keep]}).status_code == 200
        assert layer_of(client) == "backend"


def test_extend_writes_and_clears_component_tech_and_states(tmp_path):
    """Agent doplní `card.tech` / `card.states` existující karty; `null` je smaže, prázdné odmítne."""
    def card_of(client, node_id="n0"):
        nodes = client.get("/api/view", params=SCOPE).json()["graph"]["nodes"]
        return next(n for n in nodes if n["id"] == node_id).get("card")

    def item(client, **fields):
        revision = client.get("/api/desktop-v3/state", params=SCOPE).json()["revision"]
        return {"node": "@n0", "expectedRevision": revision, **fields}

    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        digest = seed(client)
        original = card_of(client)
        for bad in ({"tech": ""}, {"states": []}, {"states": ["chyba", "chyba"]}, {"tech": "x" * 81}):
            refused = send(client, digest, {"extend": [item(client, **bad)]})
            assert refused.status_code == 409, bad
            assert card_of(client) == original
        refused = send(client, digest, {"extend": [{**item(client, tech="FastAPI"), "node": "@s0"}]})
        assert refused.status_code == 409 and "tech" in refused.json()["error"]
        done = send(client, digest, {"extend": [item(client, tech="React 19", states=["prázdno", "chyba"])]})
        assert done.status_code == 200, done.text
        assert card_of(client) == {**(original or {}), "tech": "React 19", "states": ["prázdno", "chyba"]}
        cleared = send(client, done.json()["digest"], {"extend": [item(client, tech=None, states=None)]})
        assert cleared.status_code == 200, cleared.text
        assert card_of(client) == original


def test_plan_section_must_exist_on_the_nearest_page(tmp_path):
    """Agent zapíše `card.section` jen sekci nejbližší stránky; neznámou sekci i kartu mimo stránku dávka odmítne."""
    hero = {"id": "hero", "role": "hero", "name": "Hero", "intent": ""}

    def nodes_of(client):
        return {n["id"]: n for n in client.get("/api/view", params=SCOPE).json()["graph"]["nodes"]}

    def site_nodes(card):
        return {"nodes": [
            {"ref": "app", "kind": "sector", "name": "Aplikace", "site": {"kind": "application", "environments": []}},
            {"ref": "page", "kind": "node", "parent": "app", "name": "Kontakt",
             "site": {"kind": "page", "path": "/kontakt", "sections": [hero]}},
            {"ref": "ui", "kind": "node", "parent": "page", "name": "Úvod", "card": card},
        ]}

    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        digest = seed(client)
        before = nodes_of(client)
        refused = send(client, digest, site_nodes({"section": "form"}))
        assert refused.status_code == 409 and "ui" in refused.json()["error"] and "form" in refused.json()["error"]
        assert nodes_of(client) == before
        done = send(client, digest, site_nodes({"layer": "frontend", "section": "hero"}))
        assert done.status_code == 200, done.text
        ui = done.json()["refs"]["ui"]
        assert nodes_of(client)[ui]["card"] == {"layer": "frontend", "section": "hero"}

        def item(node, **fields):
            revision = client.get("/api/desktop-v3/state", params=SCOPE).json()["revision"]
            return {"node": f"@{node}", "expectedRevision": revision, **fields}

        digest = done.json()["digest"]
        for node, section, reason in ((ui, "form", "nemá sekci form"), ("n0", "hero", "mimo stránku")):
            refused = send(client, digest, {"extend": [item(node, section=section)]})
            assert refused.status_code == 409 and reason in refused.json()["error"], refused.text
        cleared = send(client, digest, {"extend": [item(ui, section=None)]})
        assert cleared.status_code == 200, cleared.text
        assert nodes_of(client)[ui]["card"] == {"layer": "frontend"}
        again = send(client, cleared.json()["digest"], {"extend": [item(ui, section="hero")]})
        assert again.status_code == 200, again.text
        assert nodes_of(client)[ui]["card"] == {"layer": "frontend", "section": "hero"}


def test_extend_writes_brief_marks_on_an_existing_area_and_sector_only_once(tmp_path):
    """Srdce dopíše značky Schránky oblasti a sektoru přijatým návrhem grafu `extend`em (návrh stav nenese)."""
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        digest = seed(client)
        revision = client.get("/api/desktop-v3/state", params=SCOPE).json()["revision"]
        marks = [{"node": "@a0", "expectedRevision": revision, "briefGroup": "logika"},
                 {"node": "@s0", "expectedRevision": revision, "briefDiscipline": "be"}]
        for bad in ({"node": "@a0", "expectedRevision": revision},  # oblast bez obsahu
                    {"node": "@a0", "expectedRevision": revision, "briefDiscipline": "be"},  # značka jiného druhu
                    {"node": "@n0", "expectedRevision": revision, "briefGroup": "logika"}):
            assert send(client, digest, {"extend": [bad]}).status_code == 409
        result = send(client, digest, {"extend": marks})
        assert result.status_code == 200, result.text
        nodes = client.get("/api/desktop-v3/state", params=SCOPE).json()["state"]["nodes"]
        assert (nodes["a0"]["briefGroup"], nodes["s0"]["briefDiscipline"]) == ("logika", "be")
        twin = {"ref": "twin", "kind": "area", "parent": None, "name": "Logika", "size": {"w": 600, "h": 400},
                "briefGroup": "logika"}
        assert send(client, result.json()["digest"], {"nodes": [twin]}).status_code == 409  # druhá značka v kontejneru
