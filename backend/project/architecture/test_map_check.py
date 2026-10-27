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


def test_journey_findings_go_first_broken_then_unrealized_segments():
    def steps(*pages):
        return [{"id": f"k{index}", "page": item} for index, item in enumerate(pages)]

    app = node("app", kind="sector", site={"kind": "application", "environments": [], "journeys": [
        {"id": "ok", "name": "Prochází", "steps": steps("a", "b")},
        {"id": "gone", "name": "Bez cíle", "steps": steps("nav", "smazana")},
        {"id": "cut", "name": "Přerušená", "steps": steps("b", "a", "b")}]})
    graph = {"nodes": [app, page("a", goal="g"), page("b", goal="g")],
             "edges": [edge("e1", "a", "b", carries="navigation")]}
    result = check_map(graph)
    assert [(f["rule"], f["journeyId"]) for f in result["findings"]] == [("journey.broken", "gone"),
                                                                        ("journey.unrealized", "cut")]
    assert result["findings"][0]["message"] == "Cesta Bez cíle: chybí stránka smazana v kroku k1."
    assert result["findings"][1]["message"] == ("Cesta Přerušená: z /b na /a nevede vazba "
                                                "(navigation, command, data ani sekce stránky).")
    assert result["summary"]["journey.broken"] == 1 and result["summary"]["journey.unrealized"] == 1
    assert RULES[:2] == ("journey.broken", "journey.unrealized")


def test_via_section_must_exist_on_the_page_of_the_previous_step():
    """`journey.via-unknown`: sekce přechodu se hledá na stránce kroku, na který krok navazuje (`after`, jinak předchozí)."""
    def via(section):
        return {"do": "click", "section": section}

    app = node("app", kind="sector", site={"kind": "application", "environments": [], "journeys": [
        {"id": "j", "name": "Kurz", "steps": [
            {"id": "k0", "page": "nav"}, {"id": "k1", "page": "a", "via": via("hero")},
            {"id": "k2", "page": "b", "label": "Prodej", "via": via("cta")},
            {"id": "k3", "page": "c", "via": via("form")}, {"id": "k4", "page": "c", "after": "k1", "via": via("cta")},
            {"id": "k5", "page": "smazana"}, {"id": "k6", "page": "a", "via": via("cokoli")},
            {"id": "k7", "page": "b", "via": {"do": "submit"}}]}]})
    graph = {"nodes": [app, page("a", goal="g", sections=[{"id": "cta"}]), page("b", goal="g", sections=[{"id": "form"}]),
                       page("c", goal="g")], "edges": []}
    via_findings = [f for f in check_map(graph)["findings"] if f["rule"] == "journey.via-unknown"]
    # k1 za menu (menu sekce nemá), k3 po b s form v pořádku, k4 odbočí z k1 (a má cta), k6 po smazané stránce se nehodnotí.
    assert [f["message"] for f in via_findings] == [
        "Cesta Kurz: krok k1 čeká akci v sekci hero, kterou menu nemá."]
    graph["nodes"][1]["site"]["sections"] = [{"id": "hero"}]
    assert [f["message"] for f in check_map(graph)["findings"] if f["rule"] == "journey.via-unknown"] == [
        "Cesta Kurz: krok k1 čeká akci v sekci hero, kterou menu nemá.",
        "Cesta Kurz: krok Prodej čeká akci v sekci cta, kterou stránka /a nemá.",
        "Cesta Kurz: krok k4 čeká akci v sekci cta, kterou stránka /a nemá."]
    assert {f["journeyId"] for f in via_findings} == {"j"} and RULES[2] == "journey.via-unknown"


def test_unverified_journey_is_reported_only_when_runs_are_given():
    """`journey.unverified` (docs/brana-cesty.md §4): bez dokladu, se zastaralým nebo neprošlým; rozbitá cesta ne."""
    from backend.project.architecture.journey_plan import journey_plan

    def steps(*pages):
        return [{"id": f"k{index}", "page": item} for index, item in enumerate(pages)]

    app = node("app", kind="sector", site={"kind": "application", "environments": [], "journeys": [
        {"id": "bez", "name": "Bez dokladu", "steps": steps("a", "b")},
        {"id": "stara", "name": "Stará", "steps": steps("a", "b")},
        {"id": "padla", "name": "Padlá", "steps": steps("a", "b")},
        {"id": "ok", "name": "Prošlá", "steps": steps("a", "b")},
        {"id": "gone", "name": "Bez cíle", "steps": steps("nav", "smazana")}]})
    graph = {"nodes": [app, page("a", goal="g"), page("b", goal="g")],
             "edges": [edge("e1", "a", "b", carries="navigation")]}

    def run(journey, digest=None, ok=True, reason=None):
        segment = {"from": "k0", "to": "k1", "ok": ok, **({"reason": reason} if reason else {})}
        return {"applicationId": "app", "journeyId": journey, "at": "2026-10-27T21:40:00Z", "command": "runner",
                "planDigest": digest or journey_plan(graph, journey)["digest"], "segments": [segment], "passed": ok}

    runs = {("app", "stara"): run("stara", digest="sha256:" + "0" * 64), ("app", "padla"): run("padla", ok=False, reason="404"),
            ("app", "ok"): run("ok")}
    assert all(f["rule"] != "journey.unverified" for f in check_map(graph)["findings"])
    findings = [f for f in check_map(graph, runs)["findings"] if f["rule"].startswith("journey.")]
    assert findings == [
        {"rule": "journey.broken", "journeyId": "gone", "message": "Cesta Bez cíle: chybí stránka smazana v kroku k1."},
        {"rule": "journey.unverified", "journeyId": "bez", "message": "Cesta Bez dokladu: chybí ověření (doklad přehrání cesty)."},
        {"rule": "journey.unverified", "journeyId": "stara",
         "message": "Cesta Stará: ověření je zastaralé, mapa se od běhu změnila."},
        {"rule": "journey.unverified", "journeyId": "padla", "message": "Cesta Padlá: neprošel přechod k0 → k1 (404)."}]
    assert check_map(graph, runs)["summary"]["journey.unverified"] == 3
    assert RULES[3] == "journey.unverified"
