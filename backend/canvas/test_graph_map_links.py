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


def comment(comment_id, parent_id=None, **overrides):
    item = {
        "id": comment_id,
        "parentId": parent_id,
        "kind": "comment",
        "name": comment_id,
        "purpose": "",
        "x": 0,
        "y": 0,
    }
    item.update(overrides)
    return item


def area(area_id, parent_id=None, size=None, **overrides):
    item = {
        "id": area_id,
        "parentId": parent_id,
        "kind": "area",
        "name": area_id,
        "purpose": "",
        "x": 0,
        "y": 0,
        "size": {"w": 500, "h": 500} if size is None else size,
    }
    item.update(overrides)
    return item


def test_comment_is_accepted_as_a_sticky_note_on_a_layer():
    graph = {"nodes": [node("layer"), comment("note-1", "layer")], "edges": []}
    assert validate_graph(graph) == graph


def test_comment_with_source_ref_is_rejected():
    graph = {"nodes": [comment("note-1", sourceRef=None)], "edges": []}
    with pytest.raises(ValueError):
        validate_graph(graph)


def test_comment_as_parent_of_another_node_is_rejected():
    graph = {"nodes": [comment("note-1"), node("child", "note-1")], "edges": []}
    with pytest.raises(ValueError):
        validate_graph(graph)


def test_edge_touching_a_comment_is_rejected():
    graph = {
        "nodes": [node("a"), comment("note-1")],
        "edges": [{"id": "e1", "source": "a", "target": "note-1"}],
    }
    with pytest.raises(ValueError):
        validate_graph(graph)


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


def test_area_with_size_and_empty_name_is_accepted():
    graph = {"nodes": [area("region-1", name="")], "edges": []}
    assert validate_graph(graph) == graph


def test_area_without_size_is_rejected():
    broken = {
        "id": "region-1", "parentId": None, "kind": "area",
        "name": "Oblast", "purpose": "", "x": 0, "y": 0,
    }
    with pytest.raises(ValueError):
        validate_graph({"nodes": [broken], "edges": []})


def test_non_area_with_size_is_rejected():
    graph = {"nodes": [node("n1")], "edges": []}
    graph["nodes"][0]["size"] = {"w": 500, "h": 500}
    with pytest.raises(ValueError):
        validate_graph(graph)


@pytest.mark.parametrize("size", [{"w": 100, "h": 500}, {"w": 500, "h": 30000}, {"w": "x", "h": 500}])
def test_area_with_out_of_range_size_is_rejected(size):
    with pytest.raises(ValueError):
        validate_graph({"nodes": [area("region-1", size=size)], "edges": []})


def test_area_with_source_ref_is_rejected():
    graph = {"nodes": [area("region-1", sourceRef=None)], "edges": []}
    with pytest.raises(ValueError):
        validate_graph(graph)


def test_area_as_parent_of_another_node_is_rejected():
    graph = {"nodes": [area("region-1"), node("child", "region-1")], "edges": []}
    with pytest.raises(ValueError):
        validate_graph(graph)


def test_flow_edge_to_a_non_area_node_is_rejected():
    graph = {
        "nodes": [area("region-1"), node("n1")],
        "edges": [{"id": "e1", "source": "region-1", "target": "n1", "port": "flow"}],
    }
    with pytest.raises(ValueError):
        validate_graph(graph)


def test_non_flow_edge_between_two_areas_is_rejected():
    graph = {
        "nodes": [area("region-1"), area("region-2")],
        "edges": [{"id": "e1", "source": "region-1", "target": "region-2"}],
    }
    with pytest.raises(ValueError):
        validate_graph(graph)


def test_flow_edge_between_two_areas_is_accepted():
    graph = {
        "nodes": [area("region-1"), area("region-2")],
        "edges": [{"id": "e1", "source": "region-1", "target": "region-2", "port": "flow"}],
    }
    assert validate_graph(graph) == graph
