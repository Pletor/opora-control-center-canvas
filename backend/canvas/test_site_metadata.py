"""Hosts and routes are metadata on ordinary graph identities, not provisioning."""
import copy

import pytest

from backend.canvas.graph import validate_graph
from backend.canvas.site_metadata import card_section_error, host_key, nearest_page
from backend.canvas.test_graph_card import node


def application(identifier="app", host="app.example.cz"):
    return node(identifier, kind="sector", site={"kind": "application", "environments": [
        {"name": "Produkce", "host": host}, {"name": "Vývoj", "host": "localhost:3000"},
    ]})


def page(identifier="page", parent="app", path="/"):
    return node(identifier, parent_id=parent, site={"kind": "page", "path": path})


def test_legacy_graph_and_application_with_no_hosts_are_valid():
    validate_graph({"nodes": [node()], "edges": []})
    app = application()
    app["site"]["environments"] = []
    validate_graph({"nodes": [app, page()], "edges": []})


def test_same_route_in_two_applications_and_nested_page_are_valid():
    other = application("marketing", "www.example.cz")
    other["site"]["environments"] = other["site"]["environments"][:1]
    graph = {"nodes": [application(), other, page(), page("home", "marketing"),
                       page("detail", "page", "/detail")], "edges": []}
    assert validate_graph(graph) == graph


@pytest.mark.parametrize("host", [None, 4, "", "https://app.example.cz", "app.example.cz/path",
                                   "app.example.cz?x", "person@app.example.cz", "app.example.cz:",
                                   "localhost:0", "localhost:65536", "bad host", "-bad.test", "a..test"])
def test_invalid_host_is_rejected(host):
    with pytest.raises(ValueError):
        validate_graph({"nodes": [application(host=host)], "edges": []})


def test_host_comparison_normalizes_dns_case_trailing_dot_and_idna():
    assert host_key("APP.Example.CZ.") == host_key("app.example.cz")
    assert host_key("localhost:3000") != host_key("localhost:3001")
    assert host_key("[::1]:3000") == ("::1", 3000)
    assert host_key("münich.example") == host_key("xn--mnich-kva.example")


def test_duplicate_host_and_environment_name_rejected():
    duplicate_host = application("other", "APP.EXAMPLE.CZ.")
    with pytest.raises(ValueError, match="host"):
        validate_graph({"nodes": [application(), duplicate_host], "edges": []})
    app = application()
    app["site"]["environments"][1]["name"] = "produkce"
    with pytest.raises(ValueError, match="prostředí"):
        validate_graph({"nodes": [app], "edges": []})


@pytest.mark.parametrize("path", ["login", "//login", "/../login", "/%2e%2e/login", "/a?x=1", "/a#x", "/with space"])
def test_invalid_page_route_is_rejected(path):
    with pytest.raises(ValueError):
        validate_graph({"nodes": [application(), page(path=path)], "edges": []})


def test_page_requires_application_ancestor_and_unique_route():
    with pytest.raises(ValueError, match="pod aplikaci"):
        validate_graph({"nodes": [page(parent=None)], "edges": []})
    with pytest.raises(ValueError, match="už v aplikaci"):
        validate_graph({"nodes": [application(), page(path="/login"), page("second", path="/login/")], "edges": []})


@pytest.mark.parametrize("site", [None, "page", {"kind": "unknown"}, {"kind": "page", "path": "/", "extra": True}])
def test_unknown_or_malformed_site_never_bypasses_graph_validation(site):
    candidate = page()
    candidate["site"] = copy.deepcopy(site)
    with pytest.raises(ValueError):
        validate_graph({"nodes": [candidate, application()], "edges": []})


def page_with(**fields):
    candidate = page()
    candidate["site"].update(fields)
    return candidate


SECTIONS = [{"id": "hero", "role": "hero", "name": "Hero", "intent": "Ozveme se do 24 h"},
            {"id": "form", "role": "cta", "name": "Formulář", "intent": ""}]


def test_page_carries_goal_feel_nav_label_and_sections_without_defaults():
    candidate = page_with(goal="Poptávka odeslaná do 2 minut", feel="klidně, důvěryhodně",
                          navLabel="Kontakt", sections=copy.deepcopy(SECTIONS))
    graph = {"nodes": [application(), candidate], "edges": []}
    stored = copy.deepcopy(graph)
    assert validate_graph(graph) == stored
    bare = page()
    validate_graph({"nodes": [application(), bare], "edges": []})
    assert bare["site"] == {"kind": "page", "path": "/"}


@pytest.mark.parametrize("key,limit", [("goal", 200), ("feel", 120), ("navLabel", 40)])
def test_page_text_length_bounds(key, limit):
    validate_graph({"nodes": [application(), page_with(**{key: "x"})], "edges": []})
    validate_graph({"nodes": [application(), page_with(**{key: "x" * limit})], "edges": []})
    for value in ("", "   ", "x" * (limit + 1), "a\0b", "a\nb", 4, None):
        with pytest.raises(ValueError, match=key):
            validate_graph({"nodes": [application(), page_with(**{key: value})], "edges": []})


def test_section_bounds_and_count():
    longest = {"id": "s" * 80, "role": "custom", "name": "n" * 60, "intent": "i" * 200}
    validate_graph({"nodes": [application(), page_with(sections=[longest])], "edges": []})
    twenty = [{"id": f"s{i}", "role": "content", "name": "Obsah", "intent": ""} for i in range(20)]
    validate_graph({"nodes": [application(), page_with(sections=twenty)], "edges": []})
    for sections in ([], twenty + [{"id": "s20", "role": "content", "name": "Obsah", "intent": ""}], {"id": "x"}, None):
        with pytest.raises(ValueError, match="sekc"):
            validate_graph({"nodes": [application(), page_with(sections=sections)], "edges": []})


@pytest.mark.parametrize("change,message", [
    ({"role": "banner"}, "role"),
    ({"role": None}, "role"),
    ({"id": "bad id"}, "id sekce"),
    ({"id": "s" * 81}, "id sekce"),
    ({"name": ""}, "název"),
    ({"name": "n" * 61}, "název"),
    ({"intent": "i" * 201}, "záměr"),
    ({"intent": "a\0b"}, "záměr"),
    ({"extra": True}, "přesně"),
])
def test_invalid_section_is_rejected(change, message):
    section = {"id": "hero", "role": "hero", "name": "Hero", "intent": ""} | change
    with pytest.raises(ValueError, match=message):
        validate_graph({"nodes": [application(), page_with(sections=[section])], "edges": []})


def test_missing_section_key_and_duplicate_section_id_are_rejected():
    with pytest.raises(ValueError, match="přesně"):
        validate_graph({"nodes": [application(), page_with(sections=[{"id": "hero", "role": "hero", "name": "Hero"}])],
                        "edges": []})
    duplicate = copy.deepcopy(SECTIONS)
    duplicate[1]["id"] = "hero"
    with pytest.raises(ValueError, match="opakuje"):
        validate_graph({"nodes": [application(), page_with(sections=duplicate)], "edges": []})


def test_application_does_not_accept_page_fields():
    app = application()
    app["site"]["goal"] = "Cíl"
    with pytest.raises(ValueError, match="aplikace"):
        validate_graph({"nodes": [app], "edges": []})


def journey(identifier="poptavka", start="nav", end="dekujeme", name="Poptávka z menu"):
    return {"id": identifier, "name": name, "from": start, "to": end}


def test_application_carries_journeys_without_defaults_and_keeps_health_path():
    app = application()
    app["site"] = {**app["site"], "healthPath": "/api/health",
                   "journeys": [journey(), journey("z-domu", "home", "dekujeme", "Z domovské stránky")]}
    saved = copy.deepcopy(app)
    validate_graph({"nodes": [app, page("home"), page("dekujeme", path="/dekujeme")], "edges": []})
    assert app == saved


def test_journey_to_a_missing_page_is_saved_and_left_to_the_map_check():
    app = application()
    app["site"]["journeys"] = [journey(end="smazana-stranka")]
    validate_graph({"nodes": [app, page()], "edges": []})


@pytest.mark.parametrize("journeys", [
    [],
    [journey()] * 2,
    [journey(name="")],
    [journey(name="   ")],
    [journey(name="x" * 81)],
    [journey(end="nav")],
    [journey(start="dekujeme")],
    [journey(start="bad id")],
    [{**journey(), "steps": []}],
    [{k: v for k, v in journey().items() if k != "to"}],
    [journey() for _ in range(21)],
    "poptavka",
])
def test_malformed_journeys_are_rejected(journeys):
    app = application()
    app["site"]["journeys"] = journeys
    with pytest.raises(ValueError):
        validate_graph({"nodes": [app, page()], "edges": []})


def test_card_section_error_reads_the_nearest_page():
    def item(identifier, parent=None, **extra):
        return {"id": identifier, "parentId": parent, "kind": "node", "name": identifier, **extra}

    sections = [{"id": "hero", "role": "hero", "name": "Hero", "intent": ""}]
    by_id = {n["id"]: n for n in [
        item("outer", site={"kind": "page", "path": "/", "sections": sections}),
        item("inner", "outer", site={"kind": "page", "path": "/x"}),
        item("ok", "outer", card={"section": "hero"}),
        item("deep", "inner", card={"section": "hero"}),
        item("loose", card={"section": "hero"}),
        item("plain", "outer"),
    ]}
    assert nearest_page(by_id, "deep")["id"] == "inner"
    assert nearest_page(by_id, "outer") is None
    assert card_section_error(by_id, "ok") is None and card_section_error(by_id, "plain") is None
    assert "inner nemá sekci hero" in card_section_error(by_id, "deep")
    assert "mimo stránku" in card_section_error(by_id, "loose")
