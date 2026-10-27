"""Výřez mapy pro agenta (§4): jen karta pod stránkou, bez výchozích hodnot, strop a ořez."""

import json

from backend.project.architecture.node_architecture import LIMIT_BYTES, node_architecture


def node(identifier, parent=None, kind="node", name=None, **extra):
    return {"id": identifier, "parentId": parent, "kind": kind, "name": identifier if name is None else name,
            "purpose": "", "x": 0, "y": 0, **extra}


def edge(identifier, source, target, **extra):
    return {"id": identifier, "source": source, "target": target, **extra}


SECTION = {"id": "form", "role": "cta", "name": "Formulář", "intent": "Jméno, e-mail, popis"}
JOURNEY = {"id": "poptavka", "name": "Poptávka", "from": "nav", "to": "dekujeme"}


def graph(journeys=(JOURNEY,), extra_edges=()):
    app_site = {"kind": "application", "environments": [], **({"journeys": list(journeys)} if journeys else {})}
    return {"nodes": [node("app", kind="sector", site=app_site),
                      node("kontakt", "app", site={"kind": "page", "path": "/kontakt", "goal": "Poptávka do 2 minut",
                                                   "sections": [SECTION]}),
                      node("dekujeme", "kontakt", site={"kind": "page", "path": "/dekujeme"}),
                      node("formular", "kontakt", name="Formulář",
                           card={"section": "form", "states": ["prázdno", "odesílá", "chyba", "hotovo"]}),
                      node("navbar", "kontakt", name="Navbar"),
                      node("api", name="POST /api/poptavka", sourceRef={"path": "api/poptavka.py"}),
                      node("db", name="db.poptavky")],
            "edges": [edge("e0", "navbar", "formular", carries="navigation"),
                      edge("e1", "formular", "api", carries="command"), edge("e2", "api", "db", carries="data"),
                      edge("e3", "db", "dekujeme", carries="navigation"), edge("e4", "formular", "db", port="rule"),
                      *extra_edges]}


def test_component_on_a_journey_gets_its_slice_of_the_map():
    assert node_architecture(graph(), "formular") == {
        "journeys": [{"id": "poptavka",
                      "line": "nav → /kontakt[form] → POST /api/poptavka → db.poptavky → /dekujeme", "youAre": 1}],
        "page": {"path": "/kontakt", "goal": "Poptávka do 2 minut",
                 "section": {"id": "form", "role": "cta", "intent": "Jméno, e-mail, popis"}},
        "in": [{"carries": "navigation", "from": "Navbar"}],
        "out": [{"carries": "command", "to": "POST /api/poptavka", "sourceRef": "api/poptavka.py"}],
        "states": ["prázdno", "odesílá", "chyba", "hotovo"],
    }


def test_card_outside_a_page_gets_nothing_and_missing_values_are_left_out():
    data = graph(journeys=())
    assert node_architecture(data, "api") is None
    assert node_architecture(data, "app") is None
    assert node_architecture(data, "chybi") is None
    # Bez cesty, příchozí hrany, stavů, sekce, `feel` a děr: klíče chybí, nic se nedoplňuje.
    assert node_architecture(data, "navbar") == {"page": {"path": "/kontakt", "goal": "Poptávka do 2 minut"},
                                                 "out": [{"carries": "navigation", "to": "Formulář"}]}


def test_gaps_name_the_rules_that_hit_this_card_or_its_edges():
    data = graph(extra_edges=[edge("e5", "navbar", "formular")])
    data["nodes"][3]["card"]["states"] = ["hotovo"]
    assert node_architecture(data, "formular")["gaps"] == ["state.no-error", "edge.carries-unset"]
    assert node_architecture(data, "navbar")["gaps"] == ["edge.carries-unset"]


def test_nested_page_on_the_journey_finds_its_own_step():
    assert node_architecture(graph(), "dekujeme")["journeys"] == [
        {"id": "poptavka", "line": "nav → /kontakt[form] → POST /api/poptavka → db.poptavky → /dekujeme", "youAre": 4}]


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode())


def test_oversized_slice_cuts_trailing_journeys_first_and_is_marked():
    journeys = [{**JOURNEY, "id": f"cesta-{index:02d}", "name": f"Cesta {index}"} for index in range(20)]
    result = node_architecture(graph(journeys=journeys), "formular")
    assert result["truncated"] is True and size(result) <= LIMIT_BYTES
    ids = [item["id"] for item in result["journeys"]]
    assert 1 <= len(ids) < 20 and ids == [f"cesta-{index:02d}" for index in range(len(ids))]
    assert result["in"] and len(result["out"]) == 1
    assert result == node_architecture(graph(journeys=journeys), "formular")
    assert "truncated" not in node_architecture(graph(), "formular")


def test_with_one_journey_left_the_edges_are_cut_from_the_end():
    edges = [edge(f"x{index:02d}", "formular", "api", carries="command") for index in range(60)]
    result = node_architecture(graph(extra_edges=edges), "formular")
    assert result["truncated"] is True and size(result) <= LIMIT_BYTES
    assert [item["id"] for item in result["journeys"]] == ["poptavka"]
    assert result["in"] == [{"carries": "navigation", "from": "Navbar"}] and 1 < len(result["out"]) < 61
