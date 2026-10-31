"""Pořadí podle záměru: `order` smí nést jen uzel nebo sektor a jen celé číslo 1–9999."""

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


@pytest.mark.parametrize("value", [1, 101, 9999])
def test_node_and_sector_carry_order(value):
    graph = {"nodes": [node(order=value), node("s1", kind="sector", order=value, memberOf="region-1"), area()],
             "edges": []}
    assert validate_graph(graph) == graph


@pytest.mark.parametrize("item", [
    area(order=101),
    node(kind="comment", order=101),
    node(order=0),
    node(order=10000),
    node(order=True),
    node(order=101.0),
    node(order="101"),
    node(order=None),
])
def test_order_elsewhere_or_out_of_range_is_refused(item):
    with pytest.raises(ValueError):
        validate_graph({"nodes": [item], "edges": []})


def test_node_keys_stay_one_base_with_optional_keys():
    with pytest.raises(ValueError, match="Neplatný uzel"):
        validate_graph({"nodes": [node(sourceRef="a.md", size={"w": 1, "h": 1})], "edges": []})
    with pytest.raises(ValueError, match="Neplatný uzel"):
        validate_graph({"nodes": [node(unknown=1)], "edges": []})
    with pytest.raises(ValueError, match="Neplatný uzel"):
        validate_graph({"nodes": [{"id": "n1", "kind": "node", "name": "n1", "x": 0, "y": 0, "purpose": ""}], "edges": []})
