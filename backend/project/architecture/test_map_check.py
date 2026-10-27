"""Kontrola mapy (§5): každé pravidlo, nepovinná pole a deterministické pořadí."""

from backend.project.architecture.map_check import RULES, check_map


def node(identifier, parent=None, kind="node", **extra):
    return {"id": identifier, "parentId": parent, "kind": kind, "name": identifier, "purpose": "", "x": 0, "y": 0,
            **extra}


def page(identifier, parent="app", **site):
    return node(identifier, parent, site={"kind": "page", "path": f"/{identifier}", **site})


def edge(identifier, source, target, **extra):
    return {"id": identifier, "source": source, "target": target, **extra}


APP = node("app", kind="sector", site={"kind": "application", "environments": []})


def rules(result):
    return [(f["rule"], f.get("nodeId") or f.get("edgeId")) for f in result["findings"]]


def test_complete_page_has_no_findings():
    graph = {"nodes": [APP, page("kontakt", goal="Poptávka do 2 minut", sections=[{"id": "form"}]),
                       node("form", "kontakt", card={"section": "form", "states": ["prázdno", " Chyba "]}),
                       node("api", "kontakt")],
             "edges": [edge("e1", "form", "api", carries="command")]}
    result = check_map(graph)
    assert result["findings"] == []
    assert result["summary"] == {rule: 0 for rule in RULES}


def test_page_without_goal_and_unrealized_sections():
    graph = {"nodes": [APP, page("b", goal="  "), page("a", sections=[{"id": "hero"}, {"id": "form"}]),
                       node("c", "a", card={"section": "form"}), node("other", "b")],
             "edges": []}
    result = check_map(graph)
    assert rules(result) == [("page.no-goal", "a"), ("page.no-goal", "b"), ("section.unrealized", "a")]
    assert "hero" in result["findings"][2]["message"]
    assert result["summary"]["page.no-goal"] == 2 and result["summary"]["section.unrealized"] == 1


def test_section_counts_only_components_of_the_nearest_page():
    graph = {"nodes": [APP, page("outer", goal="g", sections=[{"id": "s"}]),
                       page("inner", parent="outer", goal="g", sections=[{"id": "s"}]),
                       node("deep", "inner", card={"section": "s"})],
             "edges": []}
    assert rules(check_map(graph)) == [("section.unrealized", "outer")]


def test_top_level_section_key_is_not_read():
    """Sekce se čte jen z `card.section`; starý klíč uzlu `section` komponentu nedělá realizací sekce."""
    graph = {"nodes": [APP, page("p", goal="g", sections=[{"id": "s"}]), node("c", "p", section="s")], "edges": []}
    assert rules(check_map(graph)) == [("section.unrealized", "p")]


def test_unknown_section_names_the_card():
    """Karta odkazuje na sekci, kterou nejbližší stránka nemá, nebo leží mimo stránku: `section.unknown`."""
    graph = {"nodes": [APP, page("p", goal="g", sections=[{"id": "hero"}]), page("q", parent="app", goal="g"),
                       node("ok", "p", card={"section": "hero"}), node("gone", "p", card={"section": "form"}),
                       node("bare", "q", card={"section": "hero"}), node("loose", card={"section": "hero"})],
             "edges": []}
    result = check_map(graph)
    assert rules(result) == [("section.unknown", "bare"), ("section.unknown", "gone"), ("section.unknown", "loose")]
    messages = {f["nodeId"]: f["message"] for f in result["findings"]}
    assert "form" in messages["gone"] and "mimo stránku" in messages["loose"]
    assert result["summary"]["section.unknown"] == 3


def test_command_without_receiver_and_without_error_state():
    graph = {"nodes": [APP, page("p", goal="g"), node("form", "p", card={"states": ["hotovo"]}),
                       node("ok", "p", card={"states": ["error"]}), node("loose")],
             "edges": [edge("e1", "form", "gone", carries="command"), edge("e2", "ok", "form", carries="command"),
                       edge("e3", "loose", "gone", carries="command")]}
    assert rules(check_map(graph)) == [("command.no-receiver", "form"), ("state.no-error", "form")]


def test_node_with_states_outside_page_is_a_sender_and_missing_states_mean_no_error():
    graph = {"nodes": [APP, page("p", goal="g"), node("svc", card={"states": ["načítá"]}), node("form", "p"),
                       node("api", "p")],
             "edges": [edge("e1", "svc", "api", carries="command"), edge("e2", "form", "api", carries="command",
                                                                          port="next")]}
    assert rules(check_map(graph)) == [("state.no-error", "form"), ("state.no-error", "svc")]


def test_next_edge_between_components_of_one_page_needs_carries():
    graph = {"nodes": [APP, page("p", goal="g"), page("q", goal="g"), node("a", "p"), node("b", "p"),
                       node("c", "q")],
             "edges": [edge("e2", "a", "b"), edge("e1", "a", "b", port="next"), edge("e3", "a", "b", port="rule"),
                       edge("e4", "a", "c"), edge("e5", "b", "a", carries="data"), edge("e6", "p", "a")]}
    result = check_map(graph)
    assert rules(result) == [("edge.carries-unset", "e1"), ("edge.carries-unset", "e2")]
    assert result["summary"]["edge.carries-unset"] == 2


def test_malformed_optional_fields_are_read_defensively():
    graph = {"nodes": [APP, page("p", goal=5, sections="x"), node("a", "p", card="bad")],
             "edges": [edge("e1", "a", "p", carries="command")]}
    assert rules(check_map(graph)) == [("page.no-goal", "p"), ("state.no-error", "a")]
