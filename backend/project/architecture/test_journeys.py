"""Cesty zákazníka jako trychtýř (§6): proměna A → B, kroky, odvozené segmenty, remízy podle id a důvody rozbití."""

from backend.project.architecture.journeys import derive_journeys


def node(identifier, parent=None, kind="node", name=None, **extra):
    return {"id": identifier, "parentId": parent, "kind": kind, "name": identifier if name is None else name,
            "purpose": "", "x": 0, "y": 0, **extra}


def page(identifier, parent="app", path=None, **site):
    return node(identifier, parent, site={"kind": "page", "path": path or f"/{identifier}", **site})


def edge(identifier, source, target, **extra):
    return {"id": identifier, "source": source, "target": target, **extra}


def app(*journeys, identifier="app"):
    site = {"kind": "application", "environments": []}
    return node(identifier, kind="sector", site={**site, "journeys": list(journeys)} if journeys else site)


def step(identifier, page, **extra):
    return {"id": identifier, "page": page, **extra}


def journey(identifier="poptavka", start="nav", end="dekujeme", name="Poptávka z menu"):
    """Dvoukroková cesta: jeden segment z `start` na `end` (dřívější podoba A → B)."""
    return {"id": identifier, "name": name, "steps": [step("start", start), step("end", end)]}


def contact_graph(*journeys, edges=None):
    """menu → /kontakt → Formulář[form] —command→ API —data→ DB —navigation→ /dekujeme.

    Poděkování je podstránka kontaktu, v menu není; jinak by z menu vedla rovnou na ni (`nav → /dekujeme`)."""
    return {"nodes": [app(*journeys), page("kontakt", sections=[{"id": "form", "role": "cta", "name": "F", "intent": ""}]),
                      page("dekujeme", parent="kontakt"), node("formular", "kontakt", card={"section": "form"}),
                      node("api", name="POST /api/poptavka"), node("db", name="db.poptavky")],
            "edges": edges if edges is not None else [
                edge("e1", "formular", "api", carries="command"), edge("e2", "api", "db", carries="data"),
                edge("e3", "db", "dekujeme", carries="navigation")]}


def only(graph):
    [result] = derive_journeys(graph)
    return result


def segment(graph):
    """Jediný segment dvoukrokové cesty."""
    [result] = only(graph)["segments"]
    return result


def test_contact_journey_goes_from_menu_through_the_form_section_to_the_thank_you_page():
    result = only(contact_graph(journey()))
    assert result["segments"] == [{"from": "start", "to": "end", "realized": True,
                                   "line": "nav → /kontakt[form] → POST /api/poptavka → db.poptavky → /dekujeme"}]
    assert result["steps"] == [{"id": "start", "page": "nav", "path": "nav"},
                               {"id": "end", "page": "dekujeme", "path": "/dekujeme"}]
    assert result["line"] == "nav → /dekujeme"
    assert (result["applicationId"], result["id"], result["name"]) == ("app", "poptavka", "Poptávka z menu")
    assert "broken" not in result and "purpose" not in result


VIA = {"do": "click", "section": "hero", "text": "Chci video zdarma"}


def funnel_graph():
    """Trychtýř ze zadání: přistávací stránka → kontakty → prodej → upsell, miniupsell odbočí po prodeji."""
    steps = [step("vstup", "pristavaci", label="Vstupní stránka", via={"do": "open"},
                  shift="Z „nejde mi to“ na „asi je to naučitelné“.", objection="Zase někdo, kdo chce jen prodat."),
             step("kontakt", "obsah", label="1. Stránka s obsahem zdarma", via=VIA),
             step("prodej", "nabidka", label="Prodej"),
             step("upsell", "upsell", label="Upsell"),
             step("mini", "miniupsell", label="Miniupsell", after="prodej")]
    application = app({"id": "kurz", "name": "Prodej kurzu", "purpose": "Z návštěvníka zákazník",
                       "actor": "Začínající zahrádkář", "pointA": "Rostliny mu hynou.", "pointB": "Má zelený balkon.",
                       "steps": steps})
    return {"nodes": [application, page("pristavaci", path="/"), page("obsah"), page("nabidka"), page("upsell"),
                      page("miniupsell")],
            "edges": [edge("e1", "pristavaci", "obsah", carries="navigation"),
                      edge("e2", "obsah", "nabidka", carries="navigation"),
                      edge("e3", "nabidka", "upsell", carries="navigation")]}


def test_funnel_keeps_the_human_transformation_steps_and_branches_without_counting_people():
    result = only(funnel_graph())
    assert (result["purpose"], result["actor"], result["pointA"], result["pointB"]) == (
        "Z návštěvníka zákazník", "Začínající zahrádkář", "Rostliny mu hynou.", "Má zelený balkon.")
    assert result["steps"][0] == {"id": "vstup", "page": "pristavaci", "path": "/", "label": "Vstupní stránka",
                                  "via": {"do": "open"}, "shift": "Z „nejde mi to“ na „asi je to naučitelné“.",
                                  "objection": "Zase někdo, kdo chce jen prodat."}
    assert result["steps"][1]["via"] == VIA
    assert all("rate" not in item and "count" not in item for item in result["steps"])
    assert result["steps"][4]["after"] == "prodej"
    assert result["line"] == "/ → /obsah → /nabidka → /upsell → /miniupsell"
    assert [(s["from"], s["to"], s["realized"], s["line"]) for s in result["segments"]] == [
        ("vstup", "kontakt", True, "/ → /obsah"), ("kontakt", "prodej", True, "/obsah → /nabidka"),
        ("prodej", "upsell", True, "/nabidka → /upsell"), ("prodej", "mini", False, "/nabidka → /miniupsell")]
    assert "broken" not in result


def test_journey_without_transformation_fields_gets_none_filled_in():
    graph = funnel_graph()
    journey_data = graph["nodes"][0]["site"]["journeys"][0]
    for key in ("purpose", "actor", "pointA", "pointB"):
        del journey_data[key]
    result = only(graph)
    assert not {"purpose", "actor", "pointA", "pointB"} & set(result)


def test_unrealized_segment_does_not_break_the_journey():
    result = only(contact_graph(journey(), edges=[]))
    assert "broken" not in result
    assert result["segments"] == [{"from": "start", "to": "end", "line": "nav → /dekujeme", "realized": False}]


def test_page_start_and_a_result_shown_in_a_component_return_to_its_page():
    graph = contact_graph(journey(start="kontakt"), edges=[
        edge("e1", "formular", "api", carries="command"), edge("e2", "api", "dik", carries="data")])
    graph["nodes"].append(node("dik", "dekujeme", name="Poděkování"))
    assert segment(graph)["line"] == "/kontakt[form] → POST /api/poptavka → Poděkování → /dekujeme"


def test_component_without_section_is_not_entered_from_its_page_but_may_be_passed_by_edges():
    graph = contact_graph(journey())
    graph["nodes"][3] = node("formular", "kontakt")
    assert segment(graph)["realized"] is False
    graph["edges"].append(edge("e0", "kontakt", "formular", carries="navigation"))
    assert segment(graph)["line"] == "nav → /kontakt → formular → POST /api/poptavka → db.poptavky → /dekujeme"


def test_section_that_the_page_does_not_have_does_not_count():
    graph = contact_graph(journey())
    graph["nodes"][3] = node("formular", "kontakt", card={"section": "smazana"})
    assert segment(graph)["realized"] is False


def test_event_edges_and_reversed_edges_do_not_carry_the_customer():
    edges = [edge("e1", "formular", "api", carries="event"), edge("e2", "api", "db", carries="data"),
             edge("e3", "db", "dekujeme", carries="navigation")]
    assert segment(contact_graph(journey(), edges=edges))["realized"] is False
    edges = [edge("e1", "api", "formular", carries="command"), *edges[1:]]
    assert segment(contact_graph(journey(), edges=edges))["realized"] is False


def test_menu_holds_only_top_level_pages_and_the_journey_never_returns_to_it():
    graph = {"nodes": [app(journey(end="b")), page("a"), page("sub", parent="a"), page("b", parent="sub")],
             "edges": [edge("e1", "sub", "b", carries="navigation")]}
    assert segment(graph)["realized"] is False
    graph["edges"].append(edge("e2", "a", "sub", carries="navigation"))
    assert segment(graph)["line"] == "nav → /a → /sub → /b"


def test_target_in_the_menu_is_reached_straight_from_the_menu():
    assert segment({"nodes": [app(journey(end="home")), page("home", path="/")], "edges": []})["line"] == "nav → /"


def test_shortest_path_wins_and_ties_go_to_smaller_ids():
    graph = {"nodes": [app(journey(start="a", end="z")), page("a"), page("z"), node("m2", name="M2"),
                       node("m1", name="M1"), node("long")],
             "edges": [edge("e1", "a", "m2", carries="data"), edge("e2", "a", "m1", carries="data"),
                       edge("e3", "m1", "z", carries="navigation"), edge("e4", "m2", "z", carries="navigation"),
                       edge("e5", "a", "long", carries="data"), edge("e6", "long", "m1", carries="data")]}
    assert segment(graph)["line"] == "/a → M1 → /z"


def test_missing_pages_and_pages_of_another_application_break_the_journey():
    graph = {"nodes": [app(journey("j1", "smazana", "b"), journey("j2", "a", "smazana"), journey("j3", "a", "cizi")),
                       page("a"), page("b"), app(identifier="jina"), page("cizi", parent="jina")], "edges": []}
    results = {item["id"]: item for item in derive_journeys(graph)}
    assert {key: item["broken"] for key, item in results.items()} == {
        "j1": "chybí stránka smazana v kroku start.", "j2": "chybí stránka smazana v kroku end.",
        "j3": "chybí stránka cizi v kroku end."}
    assert results["j2"]["steps"] == [{"id": "start", "page": "a", "path": "/a"},
                                      {"id": "end", "page": "smazana", "missing": True}]
    assert "segments" not in results["j2"] and "line" not in results["j2"]


def test_broken_reason_names_the_step_role_when_it_has_one():
    graph = {"nodes": [app({"id": "j", "name": "J", "steps": [step("a", "nav"), step("b", "x", label="Upsell")]}),
                       page("a")], "edges": []}
    assert only(graph)["broken"] == "chybí stránka x v kroku Upsell."


def test_wrapper_sector_between_application_and_page_keeps_the_page_in_the_menu():
    graph = {"nodes": [app(journey(end="b")), node("wrap", "app", kind="sector"), page("b", parent="wrap")], "edges": []}
    assert segment(graph)["line"] == "nav → /b"


def test_applications_in_id_order_journeys_in_human_order_and_malformed_items_skipped():
    graph = {"nodes": [app(journey("z", "a", "b"), journey("y", "b", "a"), identifier="app2"), page("a", parent="app2"),
                       page("b", parent="app2"), app(journey("x", "c", "d"), "bad", {"name": "bez id"}),
                       page("c"), page("d")],
             "edges": [edge("e1", "a", "b", carries="navigation"), edge("e2", "c", "d", carries="navigation")]}
    assert [(item["applicationId"], item["id"]) for item in derive_journeys(graph)] == [
        ("app", "x"), ("app2", "z"), ("app2", "y")]
    assert derive_journeys({"nodes": [], "edges": []}) == []
