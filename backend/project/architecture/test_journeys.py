"""Cesty zákazníka (§6): odvozené kroky, `line`, remízy podle id a důvody rozbití."""

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


def journey(identifier="poptavka", start="nav", end="dekujeme", name="Poptávka z menu"):
    return {"id": identifier, "name": name, "from": start, "to": end}


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


def test_contact_journey_goes_from_menu_through_the_form_section_to_the_thank_you_page():
    result = only(contact_graph(journey()))
    assert result["line"] == "nav → /kontakt[form] → POST /api/poptavka → db.poptavky → /dekujeme"
    assert result["steps"] == [{"label": "nav"}, {"nodeId": "formular", "label": "/kontakt[form]", "pageId": "kontakt"},
                               {"nodeId": "api", "label": "POST /api/poptavka"}, {"nodeId": "db", "label": "db.poptavky"},
                               {"nodeId": "dekujeme", "label": "/dekujeme"}]
    assert (result["applicationId"], result["id"], result["name"], result["from"], result["to"]) == (
        "app", "poptavka", "Poptávka z menu", "nav", "dekujeme")
    assert "broken" not in result


def test_page_start_and_a_result_shown_in_a_component_return_to_its_page():
    graph = contact_graph(journey(start="kontakt"), edges=[
        edge("e1", "formular", "api", carries="command"), edge("e2", "api", "dik", carries="data")])
    graph["nodes"].append(node("dik", "dekujeme", name="Poděkování"))
    assert only(graph)["line"] == "/kontakt[form] → POST /api/poptavka → Poděkování → /dekujeme"


def test_component_without_section_is_not_entered_from_its_page_but_may_be_passed_by_edges():
    graph = contact_graph(journey())
    graph["nodes"][3] = node("formular", "kontakt")
    assert "nevede souvislá řada" in only(graph)["broken"]
    graph["edges"].append(edge("e0", "kontakt", "formular", carries="navigation"))
    assert only(graph)["line"] == "nav → /kontakt → formular → POST /api/poptavka → db.poptavky → /dekujeme"


def test_section_that_the_page_does_not_have_does_not_count():
    graph = contact_graph(journey())
    graph["nodes"][3] = node("formular", "kontakt", card={"section": "smazana"})
    assert "nevede souvislá řada" in only(graph)["broken"]


def test_event_edges_and_reversed_edges_do_not_carry_the_customer():
    edges = [edge("e1", "formular", "api", carries="event"), edge("e2", "api", "db", carries="data"),
             edge("e3", "db", "dekujeme", carries="navigation")]
    assert "broken" in only(contact_graph(journey(), edges=edges))
    edges = [edge("e1", "api", "formular", carries="command"), *edges[1:]]
    assert "broken" in only(contact_graph(journey(), edges=edges))


def test_menu_holds_only_top_level_pages_and_the_journey_never_returns_to_it():
    graph = {"nodes": [app(journey(end="b")), page("a"), page("sub", parent="a"), page("b", parent="sub")],
             "edges": [edge("e1", "sub", "b", carries="navigation")]}
    assert "nevede" in only(graph)["broken"]
    graph["edges"].append(edge("e2", "a", "sub", carries="navigation"))
    assert only(graph)["line"] == "nav → /a → /sub → /b"


def test_target_in_the_menu_is_reached_straight_from_the_menu():
    assert only({"nodes": [app(journey(end="home")), page("home", path="/")], "edges": []})["line"] == "nav → /"


def test_shortest_path_wins_and_ties_go_to_smaller_ids():
    graph = {"nodes": [app(journey(start="a", end="z")), page("a"), page("z"), node("m2", name="M2"),
                       node("m1", name="M1"), node("long")],
             "edges": [edge("e1", "a", "m2", carries="data"), edge("e2", "a", "m1", carries="data"),
                       edge("e3", "m1", "z", carries="navigation"), edge("e4", "m2", "z", carries="navigation"),
                       edge("e5", "a", "long", carries="data"), edge("e6", "long", "m1", carries="data")]}
    assert only(graph)["line"] == "/a → M1 → /z"


def test_missing_pages_and_pages_of_another_application_break_the_journey():
    graph = {"nodes": [app(journey("j1", "smazana", "b"), journey("j2", "a", "smazana"), journey("j3", "a", "cizi")),
                       page("a"), page("b"), app(identifier="jina"), page("cizi", parent="jina")], "edges": []}
    broken = {item["id"]: item["broken"] for item in derive_journeys(graph)}
    assert broken == {"j1": "chybí stránka smazana, kde cesta začíná.", "j2": "chybí stránka smazana, kam cesta vede.",
                      "j3": "chybí stránka cizi, kam cesta vede."}


def test_wrapper_sector_between_application_and_page_keeps_the_page_in_the_menu():
    graph = {"nodes": [app(journey(end="b")), node("wrap", "app", kind="sector"), page("b", parent="wrap")], "edges": []}
    assert only(graph)["line"] == "nav → /b"


def test_applications_in_id_order_journeys_in_human_order_and_malformed_items_skipped():
    graph = {"nodes": [app(journey("z", "a", "b"), journey("y", "b", "a"), identifier="app2"), page("a", parent="app2"),
                       page("b", parent="app2"), app(journey("x", "c", "d"), "bad", {"name": "bez id"}),
                       page("c"), page("d")],
             "edges": [edge("e1", "a", "b", carries="navigation"), edge("e2", "c", "d", carries="navigation")]}
    assert [(item["applicationId"], item["id"]) for item in derive_journeys(graph)] == [
        ("app", "x"), ("app2", "z"), ("app2", "y")]
    assert derive_journeys({"nodes": [], "edges": []}) == []
