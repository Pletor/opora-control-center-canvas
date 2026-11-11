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


def mobile(identifier="android", platform="android", bundle="cz.example.app"):
    return node(identifier, kind="sector", site={"kind": "application", "platform": platform, "environments": [
        {"name": "Produkce", "bundleId": bundle}, {"name": "Vývoj", "bundleId": bundle + ".dev"},
    ]})


def test_mobile_application_uses_bundle_id_instead_of_host():
    graph = {"nodes": [application(), mobile(), mobile("ios", "ios", "cz.example.ios")], "edges": []}
    assert validate_graph(graph) == graph
    web = application("web2", "www.example.cz")
    web["site"]["platform"] = "web"
    validate_graph({"nodes": [web], "edges": []})


@pytest.mark.parametrize("environment", [{"name": "Produkce", "host": "app.example.cz"},
                                         {"name": "Produkce", "bundleId": "cz.example.app", "host": "app.example.cz"},
                                         {"name": "Produkce", "bundleId": "app"}, {"name": "Produkce", "bundleId": "1cz.app"},
                                         {"name": "Produkce", "bundleId": "cz..app"}, {"name": "Produkce", "bundleId": 5}])
def test_mobile_environment_requires_valid_bundle_id_and_no_host(environment):
    app = mobile()
    app["site"]["environments"] = [environment]
    with pytest.raises(ValueError):
        validate_graph({"nodes": [app], "edges": []})


def test_web_environment_rejects_bundle_id_and_unknown_platform_is_rejected():
    app = application()
    app["site"]["environments"][0] = {"name": "Produkce", "bundleId": "cz.example.app"}
    with pytest.raises(ValueError, match="host"):
        validate_graph({"nodes": [app], "edges": []})
    with pytest.raises(ValueError, match="platforma"):
        validate_graph({"nodes": [mobile(platform="windows")], "edges": []})


def test_bundle_id_is_unique_in_graph_and_mobile_has_no_health_path():
    with pytest.raises(ValueError, match="bundleId"):
        validate_graph({"nodes": [mobile(), mobile("ios", "ios", "CZ.Example.App")], "edges": []})
    app = mobile()
    app["site"]["healthPath"] = "/api/health"
    with pytest.raises(ValueError, match="healthPath"):
        validate_graph({"nodes": [app], "edges": []})


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
    longest = {"id": "s" * 80, "role": "custom", "name": "n" * 60, "intent": "i" * 600,
               "look": "l" * 300}
    validate_graph({"nodes": [application(), page_with(sections=[longest])], "edges": []})
    twenty = [{"id": f"s{i}", "role": "content", "name": "Obsah", "intent": ""} for i in range(40)]
    validate_graph({"nodes": [application(), page_with(sections=twenty)], "edges": []})
    for sections in ([], twenty + [{"id": "s40", "role": "content", "name": "Obsah", "intent": ""}], {"id": "x"}, None):
        with pytest.raises(ValueError, match="sekc"):
            validate_graph({"nodes": [application(), page_with(sections=sections)], "edges": []})


@pytest.mark.parametrize("change,message", [
    ({"role": "banner"}, "role"),
    ({"role": None}, "role"),
    ({"id": "bad id"}, "id sekce"),
    ({"id": "s" * 81}, "id sekce"),
    ({"name": ""}, "název"),
    ({"name": "n" * 61}, "název"),
    ({"intent": "i" * 601}, "záměr"),
    ({"look": ""}, "vzhled"),
    ({"look": "l" * 301}, "vzhled"),
    ({"intent": "a\0b"}, "záměr"),
    ({"extra": True}, "přesně"),
])
def test_invalid_section_is_rejected(change, message):
    section = {"id": "hero", "role": "hero", "name": "Hero", "intent": ""} | change
    with pytest.raises(ValueError, match=message):
        validate_graph({"nodes": [application(), page_with(sections=[section])], "edges": []})


def test_section_moves_is_optional_bounded_and_never_filled_in():
    """`moves` (čím sekce posouvá) je nepovinné 1–120 znaků; sekce bez něj platí dál a nic se nedoplňuje."""
    sections = [SECTIONS[0] | {"moves": "Rozptýlí obavu ze spamu."}, SECTIONS[1] | {"moves": "m" * 120}]
    candidate = page_with(sections=copy.deepcopy(sections))
    assert validate_graph({"nodes": [application(), candidate], "edges": []})["nodes"][1]["site"]["sections"] == sections
    old = page_with(sections=copy.deepcopy(SECTIONS))
    validate_graph({"nodes": [application(), old], "edges": []})
    assert all("moves" not in section for section in old["site"]["sections"])
    for value in ("", "   ", "m" * 121, "a\nb", "a\0b", 4, None):
        section = SECTIONS[0] | {"moves": value}
        with pytest.raises(ValueError, match="moves"):
            validate_graph({"nodes": [application(), page_with(sections=[section])], "edges": []})


def check_sections(sections):
    return validate_graph({"nodes": [application(), page_with(sections=sections)], "edges": []})


def sec(identifier, **extra):
    return {"id": identifier, "role": "content", "name": identifier, "intent": ""} | extra


@pytest.mark.parametrize("role", ["header", "nav", "aside", "article", "main"])
def test_new_section_roles(role):
    check_sections([sec("a", role=role)])


def test_section_box_and_parent_are_optional_and_valid():
    sections = [sec("main", box={"x": 0, "y": 0, "w": 12, "h": 40}), sec("a", parent="main", box={"x": 11, "y": 199, "w": 1, "h": 1}),
                sec("b", parent="a"), sec("c", parent="main")]
    assert check_sections(copy.deepcopy(sections))["nodes"][1]["site"]["sections"] == sections
    check_sections([sec("late", parent="first"), sec("first")])


@pytest.mark.parametrize("box", [{"x": 12, "y": 0, "w": 1, "h": 1}, {"x": -1, "y": 0, "w": 1, "h": 1},
                                 {"x": 0, "y": 200, "w": 1, "h": 1}, {"x": 0, "y": 0, "w": 0, "h": 1},
                                 {"x": 0, "y": 0, "w": 13, "h": 1}, {"x": 0, "y": 0, "w": 1, "h": 41},
                                 {"x": 0, "y": 0, "w": 1, "h": 0}, {"x": 8, "y": 0, "w": 5, "h": 1},
                                 {"x": True, "y": 0, "w": 1, "h": 1}, {"x": 0, "y": 0, "w": 1.0, "h": 1},
                                 {"x": 0, "y": 0, "w": 1}, {"x": 0, "y": 0, "w": 1, "h": 1, "z": 1}, [], None])
def test_invalid_section_box_is_rejected(box):
    with pytest.raises(ValueError, match="box"):
        check_sections([sec("a", box=box)])


@pytest.mark.parametrize("sections,message", [
    ([sec("a", parent="nic")], "takové id"),
    ([sec("a", parent="a")], "parent"),
    ([sec("a", parent=5)], "parent"),
    ([sec("a", parent="b"), sec("b", parent="a")], "cyklus"),
    ([sec("a"), sec("b", parent="a"), sec("c", parent="b"), sec("d", parent="c")], "úrovně"),
])
def test_invalid_section_parent_is_rejected(sections, message):
    with pytest.raises(ValueError, match=message):
        check_sections(sections)


def test_section_status_inspiration_and_source_are_optional_and_valid():
    sections = [sec("a", status="draft"), sec("b", status="proposed", source="scan"),
                sec("c", status="approved", source="human", inspiration={"files": ["f1", "f-2_x"]}),
                sec("d", inspiration={"url": "https://example.com/a?b=1"}), sec("e", inspiration={"note": "Klidně"}),
                sec("f", source="agent", inspiration={"files": [f"f{i}" for i in range(6)], "url": "http://x.cz",
                                                      "note": "n" * 200})]
    assert check_sections(copy.deepcopy(sections))["nodes"][1]["site"]["sections"] == sections


@pytest.mark.parametrize("extra,field", [
    ({"status": "done"}, "status"), ({"status": None}, "status"), ({"source": "client"}, "source"),
    ({"inspiration": {}}, "inspiration"), ({"inspiration": []}, "inspiration"),
    ({"inspiration": {"image": "x"}}, "inspiration"),
    ({"inspiration": {"files": []}}, "files"), ({"inspiration": {"files": [f"f{i}" for i in range(7)]}}, "files"),
    ({"inspiration": {"files": ["a b"]}}, "files"), ({"inspiration": {"files": ["f", "f"]}}, "files"),
    ({"inspiration": {"files": "f1"}}, "files"),
    ({"inspiration": {"url": "ftp://x.cz"}}, "url"), ({"inspiration": {"url": "javascript:alert(1)"}}, "url"),
    ({"inspiration": {"url": "https://" + "a" * 500}}, "url"), ({"inspiration": {"url": "https://"}}, "url"),
    ({"inspiration": {"note": ""}}, "note"), ({"inspiration": {"note": "n" * 201}}, "note"),
])
def test_invalid_section_status_source_or_inspiration_is_rejected(extra, field):
    with pytest.raises(ValueError, match=field):
        check_sections([sec("a", **extra)])


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


def step(identifier, page, **extra):
    return {"id": identifier, "page": page, **extra}


def journey(identifier="poptavka", steps=None, name="Poptávka z menu", **extra):
    return {"id": identifier, "name": name, "steps": steps or [step("vstup", "nav"), step("dik", "dekujeme")], **extra}


def funnel():
    """Trychtýř: přistávací stránka → kontakty → prodej → upsell, miniupsell odbočí po prodeji; cesta je proměna A → B."""
    return journey("trychtyr", name="Prodej kurzu", purpose="Z návštěvníka zákazník s upsellem",
                   actor="Začínající zahrádkář na balkoně", pointA="Rostliny mu hynou, neví proč, stydí se zeptat.",
                   pointB="Má zelený balkon a ví, co dělá.", steps=[
        step("vstup", "pristavaci", label="Vstupní stránka", via={"do": "open"},
             shift="Z „nejde mi to“ na „asi je to naučitelné“.", objection="Zase někdo, kdo chce jen prodat."),
        step("kontakt", "obsah", label="1. Stránka s obsahem zdarma",
             via={"do": "click", "section": "hero", "text": "Chci video zdarma"}),
        step("prodej", "nabidka", label="Prodej", via={"do": "submit"}),
        step("upsell", "upsell", label="Upsell", via={"do": "click", "text": "Přidat konzultaci"}),
        step("mini", "miniupsell", label="Miniupsell", after="prodej", via={"do": "click", "section": "smazana"}),
    ])


def test_application_carries_journeys_without_defaults_and_keeps_health_path():
    app = application()
    app["site"] = {**app["site"], "healthPath": "/api/health",
                   "journeys": [journey(), funnel(), journey("z-domu", [step("a", "home"), step("b", "dekujeme", objection="Bojí se spamu.")])]}
    saved = copy.deepcopy(app)
    validate_graph({"nodes": [app, page("home"), page("dekujeme", path="/dekujeme")], "edges": []})
    assert app == saved


def test_journey_and_step_texts_at_their_limits_are_saved():
    app = application()
    app["site"]["journeys"] = [journey(actor="x" * 80, pointA="ž" * 200, pointB="ž" * 200, purpose="p" * 200, steps=[
        step("a", "home", shift="ž" * 160, objection="o" * 120, via={"do": "open"}),
        step("b", "dekujeme", via={"do": "submit", "section": "s" * 80, "text": "t" * 60})])]
    validate_graph({"nodes": [app, page("home"), page("dekujeme", path="/dekujeme")], "edges": []})


def test_journey_to_a_missing_page_is_saved_and_left_to_the_map_check():
    app = application()
    app["site"]["journeys"] = [journey(steps=[step("a", "nav"), step("b", "smazana-stranka")])]
    validate_graph({"nodes": [app, page()], "edges": []})


@pytest.mark.parametrize("journeys", [
    [],
    [journey()] * 2,
    [journey(name="")],
    [journey(name="   ")],
    [journey(name="x" * 81)],
    [journey(purpose="")],
    [journey(purpose="x" * 201)],
    [journey(actor="")],
    [journey(actor="x" * 81)],
    [journey(pointA="   ")],
    [journey(pointA="x" * 201)],
    [journey(pointB="a\nb")],
    [journey(pointB="x" * 201)],
    [{"id": "stara", "name": "Stará podoba", "from": "nav", "to": "dekujeme"}],
    [{**journey(), "extra": 1}],
    [journey(steps=[step("a", "nav")])],
    [journey(steps=[step(f"s{index}", f"p{index}") for index in range(31)])],
    [journey(steps=[step("a", "home"), step("b", "nav")])],
    [journey(steps=[step("a", "home"), step("a", "dekujeme")])],
    [journey(steps=[step("bad id", "home"), step("b", "dekujeme")])],
    [journey(steps=[step("a", "bad id"), step("b", "dekujeme")])],
    [journey(steps=[step("a", "home", label=""), step("b", "dekujeme")])],
    [journey(steps=[step("a", "home", label="x" * 61), step("b", "dekujeme")])],
    [journey(steps=[step("a", "home", shift=""), step("b", "dekujeme")])],
    [journey(steps=[step("a", "home", shift="x" * 161), step("b", "dekujeme")])],
    [journey(steps=[step("a", "home", objection="x" * 121), step("b", "dekujeme")])],
    [journey(steps=[step("a", "home", objection="a\tb"), step("b", "dekujeme")])],
    # Zrušená pole: počet lidí a zážitek se bez migrace odmítnou.
    [journey(steps=[step("a", "home", count=5), step("b", "dekujeme")])],
    [journey(steps=[step("a", "home", experience="Ví, co dál."), step("b", "dekujeme")])],
    # Signál přechodu: první krok jen open, další jen click / submit, sekce tvarem id, text 1–60.
    [journey(steps=[step("a", "home", via={"do": "click"}), step("b", "dekujeme")])],
    [journey(steps=[step("a", "home", via={"do": "open", "text": "Reklama"}), step("b", "dekujeme")])],
    [journey(steps=[step("a", "home"), step("b", "dekujeme", via={"do": "open"})])],
    [journey(steps=[step("a", "home"), step("b", "dekujeme", via={"do": "hover"})])],
    [journey(steps=[step("a", "home"), step("b", "dekujeme", via={"section": "form"})])],
    [journey(steps=[step("a", "home"), step("b", "dekujeme", via={"do": "click", "section": "bad id"})])],
    [journey(steps=[step("a", "home"), step("b", "dekujeme", via={"do": "click", "text": ""})])],
    [journey(steps=[step("a", "home"), step("b", "dekujeme", via={"do": "click", "text": "x" * 61})])],
    [journey(steps=[step("a", "home"), step("b", "dekujeme", via={"do": "click", "note": "x"})])],
    [journey(steps=[step("a", "home"), step("b", "dekujeme", via="click")])],
    [journey(steps=[step("a", "home", after="b"), step("b", "dekujeme")])],
    [journey(steps=[step("a", "home"), step("b", "dekujeme", after="b")])],
    [journey(steps=[step("a", "home"), step("b", "dekujeme", after="c"), step("c", "x")])],
    [journey(steps=[step("a", "home"), {"id": "b"}])],
    [journey(steps=[step("a", "home"), step("b", "dekujeme", note="x")])],
    [journey(identifier=f"j{index}") for index in range(21)],
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
