"""Výřez mapy pro agenta (§4): jen karta pod stránkou, řetěz „proč“, bez výchozích hodnot, strop a ořez."""

import copy
import json

from backend.project.architecture import node_architecture as node_architecture_module
from backend.project.architecture.node_architecture import LIMIT_BYTES, node_architecture


def node(identifier, parent=None, kind="node", name=None, **extra):
    return {"id": identifier, "parentId": parent, "kind": kind, "name": identifier if name is None else name,
            "purpose": "", "x": 0, "y": 0, **extra}


def edge(identifier, source, target, **extra):
    return {"id": identifier, "source": source, "target": target, **extra}


SECTION = {"id": "form", "role": "cta", "name": "Formulář", "intent": "Jméno, e-mail, popis"}
SHIFT = "Z „asi bych měl“ na „chci prohlídku, vím, co to stojí“."
OBJECTION = "Bojí se, že ho zavalíme telefonáty."
POINTS = {"actor": "Majitel zanedbané zahrady", "pointA": "Zahrada ho tíží a bojí se ceny.",
          "pointB": "Má plán, pevnou cenu a termín."}
INTO_FORM = {"do": "click", "section": "nav", "text": "Kontakt"}
SUBMIT = {"do": "submit", "section": "form", "text": "Odeslat poptávku"}
JOURNEY = {"id": "poptavka", "name": "Poptávka", "purpose": "Z návštěvníka poptávka", **POINTS, "steps": [
    {"id": "menu", "page": "nav", "label": "Menu", "via": {"do": "open"}},
    {"id": "formular", "page": "kontakt", "label": "Poptávkový formulář", "shift": SHIFT, "objection": OBJECTION,
     "via": INTO_FORM},
    {"id": "dik", "page": "dekujeme", "label": "Poděkování", "via": SUBMIT},
    {"id": "blog", "page": "blog", "label": "Blog", "after": "formular"}]}


def graph(journeys=(JOURNEY,), extra_edges=()):
    app_site = {"kind": "application", "environments": [], **({"journeys": copy.deepcopy(list(journeys))} if journeys else {})}
    return {"nodes": [node("app", kind="sector", site=app_site),
                      node("kontakt", "app", site={"kind": "page", "path": "/kontakt", "goal": "Poptávka do 2 minut",
                                                   "sections": [SECTION]}),
                      node("dekujeme", "kontakt", site={"kind": "page", "path": "/dekujeme"}),
                      node("blog", "app", site={"kind": "page", "path": "/blog"}),
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
        "journeys": [{"id": "poptavka", "name": "Poptávka", "purpose": "Z návštěvníka poptávka", **POINTS,
                      "youAre": {"step": "formular", "index": 1}, "label": "Poptávkový formulář",
                      "shift": SHIFT, "objection": OBJECTION,
                      "previous": {"step": "menu", "label": "Menu", "path": "nav", "realized": True, "via": INTO_FORM},
                      "next": [{"step": "dik", "label": "Poděkování", "path": "/dekujeme", "realized": True,
                                "via": SUBMIT},
                               {"step": "blog", "label": "Blog", "path": "/blog", "realized": False}]}],
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
    data["nodes"][4]["card"]["states"] = ["hotovo"]
    assert node_architecture(data, "formular")["gaps"] == ["state.no-error", "edge.carries-unset"]
    assert node_architecture(data, "navbar")["gaps"] == ["edge.carries-unset"]


def test_nested_page_on_the_journey_finds_its_own_step():
    assert node_architecture(graph(), "dekujeme")["journeys"] == [
        {"id": "poptavka", "name": "Poptávka", "purpose": "Z návštěvníka poptávka", **POINTS,
         "youAre": {"step": "dik", "index": 2}, "label": "Poděkování",
         "previous": {"step": "formular", "label": "Poptávkový formulář", "path": "/kontakt", "realized": True,
                      "via": SUBMIT}}]


def test_journey_with_a_missing_page_still_tells_the_card_its_role_without_realization():
    data = graph()
    data["nodes"] = [item for item in data["nodes"] if item["id"] != "blog"]
    data["nodes"][0]["site"]["journeys"][0]["steps"][3]["page"] = "smazana"
    [journey] = node_architecture(data, "formular")["journeys"]
    assert journey["previous"] == {"step": "menu", "label": "Menu", "path": "nav", "via": INTO_FORM}
    assert journey["next"] == [{"step": "dik", "label": "Poděkování", "path": "/dekujeme", "via": SUBMIT},
                               {"step": "blog", "label": "Blog"}]


def test_component_of_a_page_off_the_journey_gets_no_journeys():
    data = graph()
    data["nodes"][0]["site"]["journeys"][0]["steps"] = [{"id": "a", "page": "nav"}, {"id": "b", "page": "blog"}]
    assert "journeys" not in node_architecture(data, "formular")


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
    assert result["journeys"][0]["purpose"] == "Z návštěvníka poptávka"


CUT_ORDER = (
    lambda r: r["journeys"].pop(),                         # 1. cesty od konce, dokud nezbude jedna
    lambda r: r.pop("out"),                                # 2. hrany: při shodě délek nejdřív `out`
    lambda r: r.pop("in"),
    lambda r: r["journeys"][0].pop("purpose"),             # 3. účel cesty
    lambda r: r["journeys"][0]["next"].pop(),              # 4. sousedé kromě prvního `next`, `previous.via`, `previous`
    lambda r: r["journeys"][0]["previous"].pop("via"),
    lambda r: r["journeys"][0].pop("previous"),
    lambda r: r["page"].pop("feel"),                       # 5. `feel`, pak `goal`
    lambda r: r["page"].pop("goal"),
    lambda r: r["journeys"][0].pop("objection"),           # 6. námitka
    lambda r: r.pop("journeys"),                           # 7. první cesta celá (poslední záchrana)
)


def test_each_cut_stage_in_its_exact_order_stops_as_soon_as_the_slice_fits(monkeypatch):
    """Strop nastavený přesně na velikost výřezu po k-tém ořezu: `_fit` musí skončit právě tam (pořadí §4.3)."""
    second = {**JOURNEY, "id": "druha", "name": "Druhá"}
    data = graph(journeys=(JOURNEY, second))
    data["nodes"][1]["site"]["feel"] = "klidně"
    monkeypatch.setattr(node_architecture_module, "LIMIT_BYTES", 10 ** 6)
    expected = node_architecture(data, "formular")
    assert len(expected["journeys"]) == 2 and expected["in"] and expected["out"]
    for cut in CUT_ORDER:
        cut(expected)
        stage = {**copy.deepcopy(expected), "truncated": True}
        monkeypatch.setattr(node_architecture_module, "LIMIT_BYTES", size(stage))
        assert node_architecture(data, "formular") == stage
    # Až po sedmém stupni zůstane jen stránka se sekcí, stavy a díry; řetěz „proč“ do té doby přežije.
    assert set(stage) == {"page", "states", "truncated"} and stage["page"]["section"]["id"] == "form"


def test_worst_case_journey_at_its_limits_keeps_the_why_chain_under_the_ceiling():
    """Textová pole kontraktu na maximu limitů (diakritika v A, B a posunu dvoubajtová, `docs/cesta-zakaznika-a-brief.md`
    §4.2), běžná id, 28 sousedů, 30 hran a 8 stavů po 40 znacích: A, B, posun, první `next` a sekce zůstanou."""
    section = {"id": "formular", "role": "form", "name": "N" * 60, "intent": "i" * 200}
    via = {"do": "submit", "section": "formular", "text": "t" * 60}
    steps = [{"id": "vstup", "page": "nav", "label": "l" * 60, "via": {"do": "open"}},
             {"id": "poptavka", "page": "kontakt", "label": "l" * 60, "shift": "ž" * 160, "objection": "o" * 120,
              "via": {"do": "click", "section": "hero", "text": "t" * 60}},
             *({"id": f"dalsi-{index}", "page": "dekujeme", "label": "l" * 60, "after": "poptavka", "via": via}
               for index in range(10, 38))]
    journey = {"id": "poptavka-zahrady", "name": "n" * 80, "purpose": "p" * 200, "actor": "a" * 80,
               "pointA": "ž" * 200, "pointB": "ž" * 200, "steps": steps}
    data = graph(journeys=[journey], extra_edges=[edge(f"x{index:02d}", "formular", "api", carries="command")
                                                  for index in range(30)])
    data["nodes"][1]["site"].update(goal="g" * 200, feel="f" * 120, sections=[section])
    data["nodes"][4]["card"] = {"section": "formular", "states": [f"{index}" + "x" * 39 for index in range(8)]}
    result = node_architecture(data, "formular")
    assert result["truncated"] is True and size(result) <= LIMIT_BYTES
    [kept] = result["journeys"]
    assert (kept["actor"], kept["pointA"], kept["pointB"], kept["shift"]) == ("a" * 80, "ž" * 200, "ž" * 200, "ž" * 160)
    assert kept["next"] == [{"step": "dalsi-10", "label": "l" * 60, "path": "/dekujeme", "realized": True, "via": via}]
    assert result["page"]["section"] == {"id": "formular", "role": "form", "intent": "i" * 200}
    assert result == node_architecture(data, "formular")


def test_section_moves_travels_with_the_section_and_survives_every_cut(monkeypatch):
    """`page.section.moves` (čím sekce posouvá) jde jen se sekcí, která ho má; ořez §4.3 sekci ani `moves` nebere."""
    data = graph()
    data["nodes"][1]["site"]["sections"] = [SECTION | {"moves": "Rozptýlí obavu ze spamu."}]
    assert node_architecture(data, "formular")["page"]["section"] == {
        "id": "form", "role": "cta", "intent": "Jméno, e-mail, popis", "moves": "Rozptýlí obavu ze spamu."}
    assert "section" not in node_architecture(data, "kontakt")["page"]  # stránka sama sekci nemá
    assert "moves" not in node_architecture(graph(), "formular")["page"]["section"]
    monkeypatch.setattr(node_architecture_module, "LIMIT_BYTES", 1)
    cut = node_architecture(data, "formular")
    assert cut["truncated"] is True and cut["page"]["section"]["moves"] == "Rozptýlí obavu ze spamu."


def test_page_in_the_menu_is_its_own_page_and_gets_its_step_shift():
    data = node_architecture(graph(), "kontakt")
    assert data["page"] == {"path": "/kontakt", "goal": "Poptávka do 2 minut"}
    assert data["journeys"][0]["youAre"] == {"step": "formular", "index": 1}
    assert (data["journeys"][0]["shift"], data["journeys"][0]["objection"]) == (SHIFT, OBJECTION)
    assert node_architecture(graph(), "dekujeme")["page"] == {"path": "/dekujeme"}


def test_journey_without_transformation_fields_fills_nothing_in():
    bare = {"id": "j", "name": "J", "steps": [{"id": "a", "page": "nav"}, {"id": "b", "page": "kontakt"}]}
    [journey] = node_architecture(graph(journeys=[bare]), "formular")["journeys"]
    assert journey == {"id": "j", "name": "J", "youAre": {"step": "b", "index": 1},
                       "previous": {"step": "a", "path": "nav", "realized": True}}


def test_journey_with_a_run_carries_only_passed_and_stale():
    """`lastRun` (docs/brana-cesty.md §4): dvě pole posledního dokladu; cesta bez dokladu klíč nemá."""
    from backend.project.architecture.journey_plan import journey_plan

    second = {"id": "druha", "name": "Druhá", "steps": [{"id": "a", "page": "nav"}, {"id": "b", "page": "kontakt"}]}
    current = graph(journeys=(JOURNEY, second))
    digest = journey_plan(current, "poptavka")["digest"]
    runs = {("app", "poptavka"): {"applicationId": "app", "journeyId": "poptavka", "planDigest": digest, "passed": False,
                                  "at": "2026-10-27T21:40:00Z", "command": "runner",
                                  "segments": [{"from": "menu", "to": "formular", "ok": False, "reason": "404"}]}}
    journeys = node_architecture(current, "formular", runs)["journeys"]
    assert journeys[0]["lastRun"] == {"passed": False, "stale": False}
    assert "lastRun" not in journeys[1]
    assert "lastRun" not in node_architecture(current, "formular")["journeys"][0]
