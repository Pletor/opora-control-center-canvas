"""Lens plánu: pohled projektu a oblasti, plán proti realitě, determinismus a limity PR Lens."""
import json

import pytest

from backend.canvas.opora_hub_store import canonical
from backend.canvas.plan_lens import MAX_EDGES, MAX_NODES, NO_COMMIT, AreaNotFound, build


def card(key, x, y, *, layer=None, path=None, origin="existing", kind="node", purpose="Dělá věc. A ještě něco."):
    item = {"id": key, "parentId": None, "kind": kind, "name": key.upper(), "purpose": purpose, "x": x, "y": y}
    if layer:
        item["card"] = {"layer": layer}
    if path is not None:
        item["sourceRef"] = {"kind": "file", "origin": origin, "path": path}
    return item


def area(key, x, y, w=1000, h=1000, name=None):
    return {"id": key, "parentId": None, "kind": "area", "name": name or key, "purpose": "Oblast.", "x": x, "y": y,
            "size": {"w": w, "h": h}}


def link(key, source, target, port="next"):
    return {"id": key, "source": source, "target": target, "port": port}


def world():
    nodes = [area("a1", 0, 0, name="Jádro"), area("a2", 2000, 0, name="Okraj"),
             card("api", 10, 10, layer="backend", path="backend/api"),
             card("ui", 300, 300, layer="frontend", path="frontend/app.tsx"),
             card("idea", 500, 500, path="backend/new.py", origin="planned"),
             card("far", 2100, 10, layer="backend", path="backend/far.py"),
             card("loose", 5000, 5000, layer="database")]
    edges = [link("e1", "ui", "api"), link("e2", "api", "idea", "block"), link("e3", "api", "far"),
             link("f1", "a1", "a2", "flow")]
    state = {"nodes": {"api": {"done": {"confirmed": True}}, "ui": {"done": {"confirmed": False}}},
             "edges": {"f1": {"handoff": "Předá data okraji. Víc nic.", "summary": "x"}}}
    reality = {"existing": ["backend/api", "frontend/app.tsx", "backend/far.py"],
               "links": [("frontend/app.tsx", "backend/api/routes.py"), ("backend/api/routes.py", "backend/far.py")],
               "graphify": {"available": True, "sourceRevision": "a" * 40}, "sha": "b" * 40,
               "repo": {"owner": "o", "name": "r"}}
    return {"nodes": nodes, "edges": edges}, state, reality


def by_id(items):
    return {item["id"]: item for item in items}


def test_project_view_has_areas_flows_and_unassigned():
    graph, state, reality = world()
    result = build(graph, state, reality, project="p1", workspace="draft")
    spec, nodes = result["spec"], by_id(result["spec"]["nodes"])
    assert result["kind"] == "plan" and result["area"] is None and result["graphify"]["available"] is True
    assert nodes["area:a1"]["kind"] == "module" and nodes["area:a1"]["badges"] == ["1/3 hotovo"]
    assert nodes["area:a1"]["delta"] == "unchanged" and nodes["area:a1"]["lane"] == "frontend"  # remíza vrstev → pořadí pruhů
    assert nodes["nezarazeno:database"]["delta"] == "added" and nodes["nezarazeno:database"]["lane"] == "database"
    flow = by_id(spec["edges"])["flow:f1"]
    assert flow["kind"] == "data" and flow["label"] == "Předá data okraji." and flow["to"] == "area:a2"
    assert result["stats"] == {"areas": 2, "cards": 5, "withCode": 3, "planned": 2, "standalone": 1, "unassigned": 1,
                               "inherited": 0, "crossAreaWithoutHandoff": 0}
    assert spec["provenance"]["head"] == spec["provenance"]["base"] == {"sha": "b" * 40}
    assert "pullRequest" not in spec["provenance"]


def test_area_view_cards_plan_vs_reality_and_code_edges():
    graph, state, reality = world()
    result = build(graph, state, reality, area="a1", project="p1", workspace="draft")
    nodes, edges = by_id(result["spec"]["nodes"]), by_id(result["spec"]["edges"])
    assert set(nodes) == {"card:api", "card:ui", "card:idea", "soused:a2"}
    assert nodes["card:api"]["files"] == [{"path": "backend/api"}] and nodes["card:api"]["badges"] == ["hotovo"]
    assert nodes["card:api"]["summary"] == "Dělá věc." and nodes["card:api"]["lane"] == "backend"
    assert nodes["card:idea"]["delta"] == "added" and nodes["card:idea"]["badges"] == ["plán"]
    assert nodes["card:idea"]["files"] == [] and nodes["card:idea"]["lane"] == "plan"
    assert nodes["soused:a2"]["kind"] == "external" and nodes["soused:a2"]["summary"] == "Předá data okraji."
    assert edges["edge:e1"]["kind"] == "call" and edges["edge:e1"]["delta"] == "unchanged"
    assert edges["edge:e2"]["kind"] == "dependency" and edges["edge:e2"]["delta"] == "added"
    code = edges["kod:ui--api"]
    assert code == {"id": "kod:ui--api", "from": "card:ui", "to": "card:api", "kind": "dependency",
                    "delta": "unchanged", "label": "kód", "emphasis": "muted"}
    crossing = [item for item in edges.values() if item["to"] == "soused:a2"]
    assert [item["from"] for item in crossing] == ["card:api"]  # vazba plánu api → far vede k sousedovi; kód jen uvnitř oblasti
    assert result["stats"]["cards"] == 3 and result["stats"]["areas"] == 1


def test_most_specific_source_path_wins():
    graph, state, reality = world()
    graph["nodes"].append(card("routes", 20, 20, layer="backend", path="backend/api/routes.py"))
    reality["existing"].append("backend/api/routes.py")
    edges = by_id(build(graph, state, reality, area="a1")["spec"]["edges"])
    assert "kod:ui--routes" in edges and "kod:ui--api" not in edges


def test_unknown_area_is_refused():
    graph, state, reality = world()
    with pytest.raises(AreaNotFound):
        build(graph, state, reality, area="api")


def test_same_inputs_give_byte_identical_spec():
    graph, state, reality = world()
    first = build(graph, state, reality, area="a1", project="p1", workspace="draft")
    graph["nodes"].reverse(), graph["edges"].reverse()
    second = build(graph, state, reality, area="a1", project="p1", workspace="draft")
    assert json.dumps(first) == json.dumps(second) and first["digest"] == second["digest"]
    assert canonical(first["spec"]) == canonical(second["spec"])
    assert list(first["spec"]) == sorted(first["spec"])


def test_limits_cut_deterministically_and_say_so():
    nodes = [area("big", 0, 0, 100000, 100000)]
    nodes += [card(f"c{index:03d}", index * 10, 0, layer="backend") for index in range(300)]
    edges = [link(f"e{a:03d}-{b}", f"c{a:03d}", f"c{(a + b) % 300:03d}") for a in range(300) for b in (1, 2)]
    result = build({"nodes": nodes, "edges": edges}, {}, {}, area="big")
    spec = result["spec"]
    assert len(spec["nodes"]) == MAX_NODES and len(spec["edges"]) <= MAX_EDGES
    assert spec["nodes"][0]["id"] == "card:c000" and spec["nodes"][-1]["id"] == "card:c255"
    assert "vynecháno 44 uzlů" in spec["summary"]
    assert {"label": "Vynecháno", "value": "44 uzlů, 0 hran", "tone": "neutral"} in spec["stats"]["chips"]
    assert spec["provenance"]["head"]["sha"] == NO_COMMIT and result["graphify"] == {"available": False}


def test_empty_plan_still_has_one_node():
    spec = build({"nodes": [], "edges": []}, {}, {})["spec"]
    assert [item["id"] for item in spec["nodes"]] == ["prazdny-plan"] and spec["lanes"][0]["id"] == "plan"


def test_odd_ids_and_long_names_fit_the_schema():
    nodes = [area("a b", 0, 0), card("x" * 200, 10, 10, purpose="Bez tečky " + "slovo " * 80)]
    nodes[1]["name"] = "N" * 300
    spec = build({"nodes": nodes, "edges": []}, {}, {}, area="a b")["spec"]
    item = spec["nodes"][0]
    assert item["id"].startswith("card:h") and len(item["id"]) <= 128
    assert len(item["label"]) == 120 and len(item["summary"]) <= 200
    assert spec["id"].startswith("opora-plan:h")
