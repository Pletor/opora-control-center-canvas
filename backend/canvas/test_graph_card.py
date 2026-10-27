"""Karta uzlu: nepovinné `card` smí nést jen uzel (`kind: "node"`) a jen známé klíče a hodnoty."""

import pytest

from backend.canvas.graph import validate_graph


def node(node_id="n1", kind="node", parent_id=None, **overrides):
    item = {
        "id": node_id,
        "parentId": parent_id,
        "kind": kind,
        "name": node_id,
        "purpose": "",
        "x": 0,
        "y": 0,
    }
    item.update(overrides)
    return item


def test_node_without_card_stays_valid():
    graph = {"nodes": [node()], "edges": []}
    assert validate_graph(graph) == graph


def test_full_card_is_accepted():
    card = {"layer": "backend", "status": "ready", "due": "2026-10-10", "model": "sonnet", "effort": "high"}
    graph = {"nodes": [node(card=card)], "edges": []}
    assert validate_graph(graph) == graph


@pytest.mark.parametrize(
    "card",
    [{"layer": "frontend"}, {"layer": "database"}, {"layer": "library"}, {"status": "draft"}, {"due": "2024-02-29"}, {"model": "fable"}, {"effort": "max"}],
)
def test_each_card_key_is_optional(card):
    validate_graph({"nodes": [node(card=card)], "edges": []})


def test_card_combines_with_source_offsets_and_sector():
    sector = node("s1", kind="sector")
    child = node(
        "n1",
        parent_id="s1",
        sourceRef={"origin": "planned", "path": "a.py", "kind": "file"},
        blockOffsets={"action": {"dx": 1, "dy": 2}},
        card={"layer": "frontend"},
    )
    validate_graph({"nodes": [sector, child], "edges": []})


@pytest.mark.parametrize(
    "card",
    [
        {},
        None,
        "task",
        ["task"],
        {"type": "task"},
        {"layer": "fe"},
        {"layer": "Frontend"},
        {"layer": ""},
        {"status": "done"},
        {"model": "gpt"},
        {"effort": "extreme"},
        {"due": "2026-13-01"},
        {"due": "2026-02-30"},
        {"due": "2026-1-01"},
        {"due": "10.10.2026"},
        {"due": ""},
        {"due": 20261010},
        {"owner": "martin"},
    ],
)
def test_invalid_card_is_rejected(card):
    with pytest.raises(ValueError):
        validate_graph({"nodes": [node(card=card)], "edges": []})


@pytest.mark.parametrize(
    "carrier",
    [
        node("sector-1", kind="sector"),
        node("note-1", kind="comment"),
        node("region-1", kind="area", size={"w": 500, "h": 500}),
    ],
)
def test_card_on_non_node_is_rejected(carrier):
    carrier["card"] = {"layer": "frontend"}
    with pytest.raises(ValueError):
        validate_graph({"nodes": [carrier], "edges": []})


# Komponenta (docs/architektura-pro-agenty.md §3.3): technologie a stavy píše agent, obě nepovinné.
@pytest.mark.parametrize(
    "card",
    [
        {"tech": "React 19 + react-hook-form"},
        {"tech": "x" * 80},
        {"states": ["prázdno", "načítá", "chyba", "hotovo"]},
        {"states": ["s"]},
        {"states": [f"stav {i}" for i in range(8)]},
        {"states": ["y" * 40]},
        {"layer": "frontend", "tech": "FastAPI", "states": ["čeká", "hotovo"]},
    ],
)
def test_component_tech_and_states_are_accepted(card):
    graph = {"nodes": [node(card=card)], "edges": []}
    assert validate_graph(graph) == graph


@pytest.mark.parametrize(
    "card",
    [
        {"tech": ""},
        {"tech": "   "},
        {"tech": " React"},
        {"tech": "x" * 81},
        {"tech": "React\n19"},
        {"tech": "React\x0019"},
        {"tech": 19},
        {"tech": None},
        {"states": []},
        {"states": "hotovo"},
        {"states": None},
        {"states": [f"stav {i}" for i in range(9)]},
        {"states": ["hotovo", "hotovo"]},
        {"states": ["Hotovo", "hotovo"]},
        {"states": [""]},
        {"states": ["  "]},
        {"states": ["chyba "]},
        {"states": ["y" * 41]},
        {"states": ["a\tb"]},
        {"states": ["ok", 1]},
    ],
)
def test_invalid_component_tech_or_states_is_rejected(card):
    with pytest.raises(ValueError):
        validate_graph({"nodes": [node(card=card)], "edges": []})


# Sekce stránky, kterou komponenta realizuje (§3.3): uložení hlídá jen tvar id, ne existenci sekce.
@pytest.mark.parametrize("section", ["form", "hero-2", "A_b", "x" * 80])
def test_card_section_with_id_shape_is_accepted(section):
    graph = {"nodes": [node(card={"section": section})], "edges": []}
    assert validate_graph(graph) == graph


@pytest.mark.parametrize("section", ["", " form", "form ", "s/1", "sekce č", "x" * 81, None, 5, ["form"]])
def test_card_section_with_bad_shape_is_rejected(section):
    with pytest.raises(ValueError, match="sekce"):
        validate_graph({"nodes": [node(card={"section": section})], "edges": []})


def test_card_section_missing_on_the_page_still_saves():
    """Smazání sekce na stránce nesmí zablokovat uložení mapy; díru hlásí kontrola mapy (`section.unknown`)."""
    app = node("app", "sector", site={"kind": "application", "environments": []})
    page = node("page", parent_id="app", site={"kind": "page", "path": "/", "sections": [
        {"id": "hero", "role": "hero", "name": "Hero", "intent": ""}]})
    graph = {"nodes": [app, page, node("c", parent_id="page", card={"section": "smazana"}),
                       node("loose", card={"section": "hero"})], "edges": []}
    assert validate_graph(graph) == graph
