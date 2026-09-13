import pytest

from backend.canvas.graph import validate_graph


def node(node_id, parent_id=None):
    return {
        "id": node_id,
        "parentId": parent_id,
        "kind": "node",
        "name": node_id,
        "purpose": "",
        "x": 0,
        "y": 0,
    }


def test_explicit_edge_can_connect_existing_nodes_in_different_layers():
    graph = {
        "nodes": [
            node("layer-a"),
            node("layer-b"),
            node("left", "layer-a"),
            node("right", "layer-b"),
        ],
        "edges": [{"id": "across", "source": "left", "target": "right"}],
    }
    assert validate_graph(graph) == graph


@pytest.mark.parametrize(
    "edge",
    [
        {"id": "missing", "source": "left", "target": "unknown"},
        {"id": "self", "source": "left", "target": "left"},
        {"id": "bad id!", "source": "left", "target": "right"},
    ],
)
def test_cross_layer_change_keeps_invalid_edge_guards(edge):
    with pytest.raises(ValueError):
        validate_graph({"nodes": [node("left"), node("right")], "edges": [edge]})
