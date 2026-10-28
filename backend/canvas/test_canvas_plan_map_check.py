"""Kontrola mapy nad dávkou plánu (docs/architektura-pro-agenty.md §5.3): nové díry = varování, dávka projde."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.canvas_plan_map_check import WARNINGS_LIMIT, map_warnings
from backend.canvas.test_canvas_plan import ORIGIN, SCOPE, send


def node(node_id, parent, **extra):
    return {"id": node_id, "parentId": parent, "kind": "node", "name": node_id, "purpose": "", "x": 0, "y": 0, **extra}


def page(node_id, sections):
    return node(node_id, "app", site={"kind": "page", "path": "/" + node_id, "goal": "Cíl",
                                      "sections": [{"id": s, "role": "hero", "name": s, "intent": ""} for s in sections]})


APP = {**node("app", None, site={"kind": "application", "environments": []}), "kind": "sector"}


def test_new_hole_is_a_warning_with_place():
    before = {"nodes": [APP, page("p1", [])], "edges": []}
    after = {"nodes": [APP, page("p1", ["hero"])], "edges": []}
    assert map_warnings(before, after) == [
        {"rule": "section.unrealized", "message": "Sekce hero nemá žádnou komponentu.", "nodeId": "p1", "place": "p1"}]


def test_pre_existing_hole_is_not_a_warning_but_a_second_one_on_the_same_card_is():
    before = {"nodes": [APP, page("p1", ["hero"])], "edges": []}
    assert map_warnings(before, before) == []
    after = {"nodes": [APP, page("p1", ["hero", "cta"])], "edges": []}
    assert [w["message"] for w in map_warnings(before, after)] == ["Sekce cta nemá žádnou komponentu."]


def test_warnings_are_capped():
    after = {"nodes": [APP, page("p1", [f"s{i}" for i in range(30)])], "edges": []}
    assert len(map_warnings({"nodes": [APP], "edges": []}, after)) == WARNINGS_LIMIT


def site_plan(sections):
    return {"nodes": [
        {"ref": "app", "kind": "sector", "name": "Aplikace", "site": {"kind": "application", "environments": []}},
        {"ref": "page", "kind": "node", "parent": "app", "name": "Přehled",
         "site": {"kind": "page", "path": "/", "goal": "Zákazník vidí stav účtu",
                  "sections": [{"id": s, "role": "hero", "name": s, "intent": ""} for s in sections]}},
    ]}


def test_batch_opening_a_hole_is_not_rejected_and_old_holes_stay_silent(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        digest = client.get("/api/view", params=SCOPE).json()["digest"]
        dry = send(client, digest, site_plan(["hero"]), dry=True)
        assert dry.status_code == 200, dry.text
        assert [w["rule"] for w in dry.json()["warnings"]] == ["section.unrealized"]
        response = send(client, digest, site_plan(["hero"]))
        assert response.status_code == 200, response.text
        page_id = response.json()["refs"]["page"]
        assert response.json()["warnings"] == [{"rule": "section.unrealized", "message": "Sekce hero nemá žádnou komponentu.",
                                                "nodeId": page_id, "place": page_id}]
        digest = client.get("/api/view", params=SCOPE).json()["digest"]
        more = send(client, digest, {"nodes": [{"ref": "note", "kind": "node", "parent": f"@{page_id}", "name": "Poznámka"}]})
        assert more.status_code == 200, more.text
        assert more.json()["warnings"] == []  # sekce hero je pořád díra, ale otevřela ji první dávka
