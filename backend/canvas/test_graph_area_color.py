"""Barva oblasti: `color` smí nést jen oblast (`kind: "area"`) a jen jednu ze šesti hodnot."""

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


def area(area_id="region-1", **overrides):
    return node(area_id, kind="area", size={"w": 500, "h": 500}, **overrides)


def test_area_without_color_stays_valid():
    graph = {"nodes": [area()], "edges": []}
    assert validate_graph(graph) == graph


def test_area_color_is_accepted():
    graph = {"nodes": [area(color="teal")], "edges": []}
    assert validate_graph(graph) == graph


@pytest.mark.parametrize("color", ["blue", "", "Indigo", "indigo ", 1, None, ["teal"]])
def test_unknown_area_color_is_rejected(color):
    with pytest.raises(ValueError):
        validate_graph({"nodes": [area(color=color)], "edges": []})


@pytest.mark.parametrize(
    "carrier",
    [node("n1"), node("sector-1", kind="sector"), node("note-1", kind="comment")],
)
def test_color_on_non_area_node_is_rejected(carrier):
    carrier["color"] = "teal"
    with pytest.raises(ValueError):
        validate_graph({"nodes": [carrier], "edges": []})
