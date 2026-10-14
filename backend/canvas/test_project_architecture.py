"""Architektura projektu: rozdělení a složení grafu, revize, historie, návrat a smazaná ID."""

import pytest

from backend.canvas.architecture_graph import EMPTY_REMOVED, compose, references, same_content, split
from backend.canvas.canvas_service import CanvasService
from backend.canvas.graph import EMPTY, validate_graph
from backend.canvas.test_graph_card import node


def domain(identifier="app", host="app.example.cz", parent=None, **extra):
    site = {"kind": "application", "environments": [{"name": "Produkce", "host": host}], **extra}
    return node(identifier, kind="sector", parent_id=parent, site=site)


def page(identifier="page", parent="app", path="/"):
    return node(identifier, parent_id=parent, site={"kind": "page", "path": path})


def test_split_takes_site_nodes_with_ancestors_and_architecture_edges():
    graph = {
        "nodes": [node("root", kind="sector"), domain(parent="root"), node("group", kind="sector", parent_id="app"),
                  page(parent="group"), node("card", parent_id="page"), node("loose", kind="sector")],
        "edges": [{"id": "e1", "source": "app", "target": "page"}, {"id": "e2", "source": "card", "target": "page"}],
    }
    arch, content = split(graph)
    assert [n["id"] for n in arch["nodes"]] == ["root", "app", "group", "page"]
    assert [e["id"] for e in arch["edges"]] == ["e1"]
    assert [n["id"] for n in content["nodes"]] == ["card", "loose"]
    assert [e["id"] for e in content["edges"]] == ["e2"]
    validate_graph(arch)


def test_node_that_loses_site_stays_only_while_it_is_an_ancestor():
    leaf = node("page")  # stránka bez site a bez potomků se stránkou → obsah
    arch, content = split({"nodes": [domain(), leaf], "edges": []})
    assert [n["id"] for n in arch["nodes"]] == ["app"]
    assert [n["id"] for n in content["nodes"]] == ["page"]
    middle = node("group", kind="sector", parent_id="app")
    arch, _content = split({"nodes": [domain(), middle, page(parent="group")], "edges": []})
    assert "group" in {n["id"] for n in arch["nodes"]}


def test_compose_prefers_architecture_and_reports_differing_copies():
    arch = {"nodes": [domain()], "edges": []}
    content = {"nodes": [domain(host="old.example.cz"), node("card", parent_id="app")], "edges": []}
    graph, conflicts = compose(arch, EMPTY_REMOVED, content)
    assert [n["id"] for n in graph["nodes"]] == ["app", "card"]
    assert graph["nodes"][0]["site"]["environments"][0]["host"] == "app.example.cz"
    assert conflicts == [{"id": "app", "name": "app", "reason": "architecture"}]
    _graph, legacy_conflicts = compose(arch, EMPTY_REMOVED, content, legacy=True)
    assert legacy_conflicts == []


def test_removed_ids_hide_legacy_copies_and_their_orphans():
    content = {"nodes": [domain("gone"), page("p", "gone"), node("card", parent_id="p"), node("free")],
               "edges": [{"id": "e", "source": "card", "target": "free"}]}
    removed = {"nodes": ["gone", "p"], "edges": []}
    graph, conflicts = compose(EMPTY, removed, content, legacy=True)
    assert [n["id"] for n in graph["nodes"]] == ["free"]
    assert graph["edges"] == [] and conflicts == []


def test_references_ignore_copies_and_count_children_and_mixed_edges():
    content = {"nodes": [domain(), page()], "edges": []}
    assert not references(content, {"app", "page"})
    assert references({"nodes": [node("card", parent_id="page")], "edges": []}, {"page"})
    assert references({"nodes": [node("card")], "edges": [{"id": "e", "source": "card", "target": "app"}]}, {"app"})


def test_same_content_ignores_order_rounding_and_moved_nodes():
    a = {"nodes": [node("x", x=10.4), node("y")], "edges": []}
    b = {"nodes": [node("y"), node("x", x=10)], "edges": []}
    assert same_content(a, b)
    assert same_content({"nodes": [*a["nodes"], domain()], "edges": []}, b, {"app"})
    assert not same_content(a, {"nodes": [node("y")], "edges": []})


def test_store_reads_empty_writes_revisions_and_restores(tmp_path):
    s = CanvasService(tmp_path / "data")
    store = s.architecture
    assert store.public("draft") == {"graph": EMPTY, "revision": 0, "digest": store.read("draft")["digest"]}
    first = {"nodes": [domain()], "edges": []}
    saved = store.save({"project": "draft", "workspace": "draft", "expectedRevision": 0, "graph": first}, actor="human")
    assert saved["revision"] == 1 and saved["graph"] == first
    with pytest.raises(ValueError, match="jiném okně"):
        store.save({"project": "draft", "workspace": "draft", "expectedRevision": 0, "graph": first})
    second = {"nodes": [domain(), page()], "edges": []}
    store.save({"project": "draft", "workspace": "draft", "expectedRevision": 1, "graph": second}, actor="agent-x")
    assert [(h["revision"], h["actor"], h["workspace"]) for h in store.history("draft")] == [
        (2, "agent-x", "draft"), (1, "human", "draft")]
    restored = store.restore({"project": "draft", "revision": 1, "digest": store.read("draft")["digest"]})
    assert restored["revision"] == 3 and restored["graph"] == first
    assert store.read("draft")["removed"] == {"nodes": ["page"], "edges": []}
    assert s.view("draft", "draft")["architectureRevision"] == 3


def test_direct_write_rejects_content_and_stale_digest_on_restore(tmp_path):
    s = CanvasService(tmp_path / "data")
    with pytest.raises(ValueError, match="Do architektury patří"):
        s.architecture.save({"project": "draft", "workspace": "draft", "expectedRevision": 0,
                             "graph": {"nodes": [node("card")], "edges": []}})
    s.architecture.save({"project": "draft", "workspace": "draft", "expectedRevision": 0,
                         "graph": {"nodes": [domain()], "edges": []}})
    with pytest.raises(ValueError, match="jiném okně"):
        s.architecture.restore({"project": "draft", "revision": 1, "digest": "stale"})


def test_health_path_is_validated_like_a_route():
    validate_graph({"nodes": [domain(healthPath="/api/v1/health")], "edges": []})
    for bad in ("api/health", "/a/../b", "/x?y", 5):
        with pytest.raises(ValueError):
            validate_graph({"nodes": [domain(healthPath=bad)], "edges": []})
    with pytest.raises(ValueError):
        validate_graph({"nodes": [domain(health="/x")], "edges": []})
