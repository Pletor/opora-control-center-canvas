"""Plán přehrání cesty (`docs/brana-cesty.md` §2): segmenty, scope, baseUrl, digest a chyby."""

import copy
import hashlib
import json

import pytest

from backend.project.architecture.journey_plan import (
    JourneyAmbiguous,
    JourneyBroken,
    JourneyNotFound,
    base_url,
    journey_digests,
    journey_plan,
)


def node(identifier, parent=None, kind="node", **extra):
    return {"id": identifier, "parentId": parent, "kind": kind, "name": identifier, "purpose": "", "x": 0, "y": 0,
            **extra}


def page(identifier, parent="web", path=None, **site):
    return node(identifier, parent, site={"kind": "page", "path": path or f"/{identifier}", **site})


KAMPAN = {"id": "kampan", "name": "Kampaň Pěstování", "steps": [
    {"id": "s0", "page": "nav"},
    {"id": "s1", "page": "home", "via": {"do": "click", "text": "Domů"}},
    {"id": "s2", "page": "novinky", "via": {"do": "submit", "section": "form", "text": "Chci video zdarma"}},
    {"id": "s3", "page": "pribeh"},
    {"id": "s4", "page": "pribeh", "after": "s1", "via": {"do": "click", "section": "cta"}}]}


def graph(*journeys, host="localhost:3000", app_id="web"):
    site = {"kind": "application", "environments": [{"name": "Dev", "host": host}] if host else [],
            "journeys": copy.deepcopy(list(journeys or (KAMPAN,)))}
    return {"nodes": [node(app_id, kind="sector", site=site),
                      page("home", app_id, path="/", sections=[{"id": "form"}, {"id": "cta"}]),
                      page("novinky", app_id), page("pribeh", app_id)],
            "edges": []}


def test_plan_lists_segments_in_journey_order_with_open_scope_do_text_and_expect_path():
    plan = journey_plan(graph(), "kampan")
    assert {key: plan[key] for key in ("schema", "applicationId", "journeyId", "name", "baseUrl")} == {
        "schema": "opora.journey-plan/1", "applicationId": "web", "journeyId": "kampan", "name": "Kampaň Pěstování",
        "baseUrl": "http://localhost:3000"}
    assert plan["segments"] == [
        {"from": "s0", "to": "s1", "open": "/", "scope": "nav", "do": "click", "text": "Domů", "expectPath": "/"},
        {"from": "s1", "to": "s2", "open": "/", "scope": '[data-opora-section="form"]', "do": "submit",
         "text": "Chci video zdarma", "expectPath": "/novinky"},
        {"from": "s2", "to": "s3", "open": "/novinky", "scope": "body", "do": "click", "expectPath": "/pribeh"},
        {"from": "s1", "to": "s4", "open": "/", "scope": '[data-opora-section="cta"]', "do": "click",
         "expectPath": "/pribeh"}]


def test_digest_is_sha256_of_compact_sorted_json_and_ignores_base_url():
    plan = journey_plan(graph(), "kampan")
    body = json.dumps({"applicationId": "web", "journeyId": "kampan", "segments": plan["segments"]},
                      ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    assert plan["digest"] == "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()
    assert journey_plan(graph(host="kampan.cz"), "kampan")["digest"] == plan["digest"]
    assert journey_digests(graph()) == {("web", "kampan"): plan["digest"]}


def test_digest_changes_with_via_and_page_path():
    before = journey_plan(graph(), "kampan")["digest"]
    changed = copy.deepcopy(KAMPAN)
    changed["steps"][2]["via"]["text"] = "Chci video"
    assert journey_plan(graph(changed), "kampan")["digest"] != before
    moved = graph()
    moved["nodes"][2]["site"]["path"] = "/aktuality"
    assert journey_plan(moved, "kampan")["digest"] != before


def test_base_url_scheme_and_missing_environment():
    assert base_url({"site": {"environments": [{"name": "D", "host": "127.0.0.1:8000"}]}}) == "http://127.0.0.1:8000"
    assert base_url({"site": {"environments": [{"name": "P", "host": "kampan.cz"}]}}) == "https://kampan.cz"
    assert base_url({"site": {"environments": []}}) is None
    assert "baseUrl" not in journey_plan(graph(host=None), "kampan")


def test_unknown_broken_and_ambiguous_journeys_have_no_plan():
    with pytest.raises(JourneyNotFound):
        journey_plan(graph(), "jina")
    broken = {"id": "rozbita", "name": "Rozbitá", "steps": [{"id": "a", "page": "nav"}, {"id": "b", "page": "smazana"}]}
    with pytest.raises(JourneyBroken, match="Cesta Rozbitá: chybí stránka smazana v kroku b."):
        journey_plan(graph(KAMPAN, broken), "rozbita")
    assert set(journey_digests(graph(KAMPAN, broken))) == {("web", "kampan")}
    two = graph()
    second = graph(app_id="shop")
    two["nodes"] += [second["nodes"][0], page("shop-home", "shop", path="/"), page("shop-novinky", "shop", path="/novinky"),
                     page("shop-pribeh", "shop", path="/pribeh")]
    shop_journey = two["nodes"][4]["site"]["journeys"][0]
    for step, target in zip(shop_journey["steps"][1:], ("shop-home", "shop-novinky", "shop-pribeh", "shop-pribeh")):
        step["page"] = target
    with pytest.raises(JourneyAmbiguous):
        journey_plan(two, "kampan")
    assert journey_plan(two, "kampan", "shop")["applicationId"] == "shop"
    with pytest.raises(JourneyNotFound):
        journey_plan(two, "kampan", "jina-aplikace")
