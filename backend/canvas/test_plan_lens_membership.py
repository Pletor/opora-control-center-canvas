"""Lens plánu: členství karty v oblasti – memberOf > samostatné > poloha > dědění > nezařazeno, a předávky."""
import json
import shutil
import subprocess

import pytest

from backend.canvas.plan_lens import build
from backend.canvas.plan_lens_membership import (
    EXPLICIT,
    GEOMETRY,
    INHERITED,
    MARKED,
    crossings,
    resolve,
)
from backend.canvas.test_plan_lens import area, by_id, card, link
from backend.canvas.test_plan_lens_code import CLI


def child(key, parent, x=10, y=10, **extra):
    item = card(key, x, y, layer="backend")
    item["parentId"] = parent
    item.update(extra)
    return item


def sub_area(key, parent, name=None):
    item = area(key, 0, 0, 500, 500, name=name)
    item["parentId"] = parent
    return item


def world():
    """Jádro a1 s kartou api; pod api dítě kid (bez oblasti) a vnuk grandkid; volná karta loose s dítětem."""
    nodes = [area("a1", 0, 0, name="Jádro"), area("a2", 2000, 0, name="Okraj"),
             card("api", 10, 10, layer="backend"), card("loose", 5000, 5000, layer="backend"),
             child("kid", "api"), child("grandkid", "kid"), child("stray", "loose")]
    return {"nodes": nodes, "edges": []}


def membership(graph):
    nodes = sorted(graph["nodes"], key=lambda item: item["id"])
    cards = [item for item in nodes if item["kind"] in ("node", "sector")]
    return resolve(cards, nodes, [item for item in nodes if item["kind"] == "area"])


def test_geometry_inheritance_and_unassigned():
    found = membership(world())
    assert found["api"] == ("a1", GEOMETRY)
    assert found["kid"] == ("a1", INHERITED) and found["grandkid"] == ("a1", INHERITED)  # nejbližší předek s oblastí
    assert found["loose"] == (None, None) and found["stray"] == (None, None)


def test_explicit_member_of_beats_geometry_and_a_dangling_one_is_ignored():
    graph = world()
    by_id(graph["nodes"])["api"]["memberOf"] = "a2"  # leží v a1, člověk řekl a2
    by_id(graph["nodes"])["loose"]["memberOf"] = "chybi"  # neexistující oblast nic nezmění
    found = membership(graph)
    assert found["api"] == ("a2", EXPLICIT) and found["kid"] == ("a2", INHERITED)
    assert found["loose"] == (None, None)


def test_marked_standalone_is_not_an_orphan_and_beats_geometry():
    graph = world()
    nodes = by_id(graph["nodes"])
    nodes["api"]["card"]["scope"] = "samostatne"  # značka člověka přebije polohu i dědění dětí
    nodes["loose"]["standalone"] = True
    found = membership(graph)
    assert found["api"] == (None, MARKED) and found["kid"] == (None, MARKED) and found["stray"] == (None, MARKED)
    result = build(graph, {}, {})
    assert result["stats"]["unassigned"] == 0
    spec_nodes = by_id(result["spec"]["nodes"])
    assert "samostatne:backend" in spec_nodes and "nezarazeno:backend" not in spec_nodes
    nodes["api"]["memberOf"] = "a1"  # výslovné členství je silnější než značka
    assert membership(graph)["api"] == ("a1", EXPLICIT)


def test_inherited_cards_show_in_the_area_with_a_badge_and_count():
    result = build(world(), {}, {}, area="a1")
    nodes = by_id(result["spec"]["nodes"])
    assert set(nodes) == {"card:api", "card:kid", "card:grandkid"}
    assert "zděděno" in nodes["card:kid"]["badges"] and "zděděno" not in nodes["card:api"]["badges"]
    assert result["stats"]["inherited"] == 2 and result["stats"]["cards"] == 3
    project = build(world(), {}, {})
    assert project["stats"]["unassigned"] == 2 and project["stats"]["inherited"] == 2
    assert by_id(project["spec"]["nodes"])["area:a1"]["subtitle"] == "karet: 3, zděděno: 2"


def conflict():
    """Dítě kid leží v oblasti b uvnitř karty api (a1): je krokem procesu b, ne a1."""
    graph = world()
    graph["nodes"].append(sub_area("b", "api", name="Platba"))
    return graph


def test_card_lying_in_another_area_than_its_parent_belongs_there_and_needs_a_handoff():
    graph = conflict()
    found = membership(graph)
    assert found["kid"] == ("b", GEOMETRY) and found["grandkid"] == ("b", INHERITED)
    cards = [item for item in graph["nodes"] if item["kind"] == "node"]
    assert crossings(cards, found, []) == [{"child": "kid", "parent": "api", "source": "a1", "target": "b", "flow": None}]
    inside = build(graph, {}, {}, area="b")
    nodes, edges = by_id(inside["spec"]["nodes"]), by_id(inside["spec"]["edges"])
    assert set(nodes) == {"card:kid", "card:grandkid", "soused:a1"} and "chybí předávka" in nodes["card:kid"]["badges"]
    missing = edges["predavka:api--kid"]
    assert (missing["from"], missing["to"], missing["kind"], missing["label"]) == ("soused:a1", "card:kid", "other",
                                                                                     "chybí předávka")
    assert "Návrh: přidat tok (flow) Jádro → Platba" in missing["summary"]
    assert inside["stats"]["crossAreaWithoutHandoff"] == 1
    parent_side = build(graph, {}, {}, area="a1")
    assert by_id(parent_side["spec"]["edges"])["predavka:api--kid"]["to"] == "soused:b"
    assert set(by_id(parent_side["spec"]["nodes"])) == {"card:api", "soused:b"}
    project = build(graph, {}, {})
    assert project["stats"]["crossAreaWithoutHandoff"] == 1 and project["stats"]["inherited"] == 1
    assert by_id(project["spec"]["edges"])["chybi:a1--b"]["label"] == "chybí předávka"
    assert "chybí předávka" in by_id(project["spec"]["nodes"])["area:b"]["badges"]
    assert build(graph, {}, {}, area="a2")["stats"]["crossAreaWithoutHandoff"] == 0  # jen dvojice, které se oblasti týkají


def test_flow_between_the_areas_is_the_handoff_with_its_report():
    graph = conflict()
    graph["edges"].append(link("f9", "a1", "b", "flow"))
    state = {"edges": {"f9": {"handoff": "Předá košík a částku. Nic dalšího."}}}
    inside = build(graph, state, {}, area="b")
    handoff = by_id(inside["spec"]["edges"])["predavka:api--kid"]
    assert handoff["kind"] == "data" and handoff["label"] == "předávka: Předá košík a částku."
    assert "chybí předávka" not in by_id(inside["spec"]["nodes"])["card:kid"]["badges"]
    project = build(graph, state, {})
    assert project["stats"]["crossAreaWithoutHandoff"] == 0 and "chybi:a1--b" not in by_id(project["spec"]["edges"])
    graph["edges"][-1] = link("f9", "b", "a1", "flow")  # tok opačným směrem předávku také nese
    assert build(graph, state, {}, area="b")["stats"]["crossAreaWithoutHandoff"] == 0


def test_parent_cycle_does_not_hang_and_stays_unassigned():
    nodes = [child("x", "y"), child("y", "x")]
    assert membership({"nodes": nodes, "edges": []}) == {"x": (None, None), "y": (None, None)}


def test_membership_is_order_independent():
    graph = conflict()
    first = build(graph, {}, {}, area="b")
    graph["nodes"].reverse()
    assert json.dumps(build(graph, {}, {}, area="b")) == json.dumps(first)


@pytest.mark.skipif(not CLI.exists() or shutil.which("node") is None, reason="připnuté PR Lens CLI chybí")
def test_membership_specs_validate_with_pinned_cli(tmp_path):
    graph = conflict()
    files = []
    for name in (None, "a1", "b"):
        target = tmp_path / f"plan-{name or 'project'}.json"
        target.write_text(json.dumps(build(graph, {}, {}, name, "p1", "draft")["spec"]), encoding="utf-8")
        files.append(str(target))
    done = subprocess.run([str(CLI), "validate", *files], capture_output=True, text=True, timeout=120, check=False)
    assert done.returncode == 0, done.stdout + done.stderr
