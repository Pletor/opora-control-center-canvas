import copy
import pytest

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.areas import area_of
from backend.canvas.canvas_layout import arrange
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed, send


def prepared(client):
    seed(client)
    view = client.get("/api/view", params=SCOPE).json()
    area = next(n for n in view["graph"]["nodes"] if n["id"] == "a0")
    area["size"] = {"w": 1100, "h": 800}
    area["parentId"] = "s0"
    area["name"] = '<script>alert("x")</script>'
    view["graph"]["nodes"].append({"id": "n1", "parentId": "s0", "kind": "node", "name": "Next", "purpose": "", "x": -500, "y": 0})
    response = client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": view["graph"], "digest": view["digest"]})
    assert response.status_code == 200, response.text
    return client.get("/api/view", params=SCOPE).json()


def test_grid_dry_run_membership_svg_and_stale_write(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        view = prepared(client)
        payload = {**SCOPE, "digest": view["digest"], "area": "@a0", "order": ["@n1", "@n0"], "columns": 2, "color": "teal", "dryRun": True}
        preview = client.post("/api/canvas-layout", headers=HEADERS, json=payload)
        assert preview.status_code == 200, preview.text
        assert client.get("/api/view", params=SCOPE).json()["digest"] == view["digest"]
        assert "<script>" not in preview.json()["svg"] and "&lt;script&gt;" in preview.json()["svg"]
        payload["dryRun"] = False
        saved = client.post("/api/canvas-layout", headers=HEADERS, json=payload)
        assert saved.status_code == 200, saved.text
        graph = saved.json()["graph"]
        cards = {n["id"]: n for n in graph["nodes"]}
        assert cards["n1"]["x"] < cards["n0"]["x"] and cards["n1"]["y"] == cards["n0"]["y"]
        assert area_of(cards["n0"], graph["nodes"])["id"] == "a0"
        assert cards["a0"]["color"] == "teal"
        assert client.post("/api/canvas-layout", headers=HEADERS, json=payload).status_code == 409
        svg = client.get("/api/layout-preview", params={**SCOPE, "layer": "s0"})
        assert svg.status_code == 200 and svg.headers["content-type"].startswith("image/svg+xml")
        assert "sandbox" in svg.headers["content-security-policy"]
        brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "s0"}).json()
        assert brief["context"]["layoutPreview"]["svg"] == svg.text


def test_bad_grid_and_batch_move_are_atomic(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        view = prepared(client)
        payload = {**SCOPE, "digest": view["digest"], "area": "@a0", "order": ["@n0", "@n1"], "columns": 3}
        # Two cards fit even if columns=3; a one-column grid requires extra height.
        bad = copy.deepcopy(payload)
        bad["order"] = ["@n0", "@n0"]
        assert client.post("/api/canvas-layout", headers=HEADERS, json=bad).status_code == 409
        assert client.get("/api/view", params=SCOPE).json()["digest"] == view["digest"]
        revision = client.get("/api/desktop-v3/state", params=SCOPE).json()["revision"]
        plan = {"extend": [{"node": "@n0", "expectedRevision": revision, "parent": "@a0", "columns": 2},
                           {"node": "@n1", "expectedRevision": revision, "parent": "@a0", "columns": 2},
                           {"node": "@a0", "expectedRevision": revision, "color": "amber"}]}
        result = send(client, view["digest"], plan)
        assert result.status_code == 200, result.text
        graph = client.get("/api/view", params=SCOPE).json()["graph"]
        assert next(n for n in graph["nodes"] if n["id"] == "a0")["color"] == "amber"
        assert all(area_of(n, graph["nodes"])["id"] == "a0" for n in graph["nodes"] if n["id"] in ("n0", "n1"))


def test_grid_rejects_insufficient_room_and_fixed_card_collision(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        graph = prepared(client)["graph"]
        small = copy.deepcopy(graph)
        next(n for n in small["nodes"] if n["id"] == "a0")["size"]["w"] = 400
        with pytest.raises(ValueError, match="nevejde"):
            arrange(small, "@a0", ["@n0"], 1)
        blocker = next(n for n in graph["nodes"] if n["id"] == "n1")
        blocker.update(x=548, y=48)
        with pytest.raises(ValueError, match="koliduje"):
            arrange(graph, "@a0", ["@n0"], 1)
