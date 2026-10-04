"""Hosts and routes are metadata on ordinary graph identities, not provisioning."""
import copy

import pytest

from backend.canvas.graph import validate_graph
from backend.canvas.site_metadata import host_key
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
