from backend.canvas.areas import area_of


def area(area_id, x, y, w, h, parent=None):
    return {
        "id": area_id, "parentId": parent, "kind": "area", "name": area_id, "purpose": "",
        "x": x, "y": y, "size": {"w": w, "h": h},
    }


def node(node_id, x, y, parent=None, kind="node"):
    return {"id": node_id, "parentId": parent, "kind": kind, "name": node_id, "purpose": "", "x": x, "y": y}


def comment(comment_id, x, y, parent=None):
    return node(comment_id, x, y, parent, kind="comment")


def test_node_inside_area_rect_belongs_to_it():
    big = area("big", 0, 0, 1000, 1000)
    n = node("n1", 100, 100)  # centre (236, 220), inside [0,1000]x[0,1000]
    nodes = [big, n]
    assert area_of(n, nodes)["id"] == "big"


def test_node_outside_area_rect_has_no_area():
    small = area("small", 0, 0, 200, 200)  # centre must be inside [0,200]x[0,200]
    n = node("n1", 100, 100)  # centre (236, 220), just outside
    nodes = [small, n]
    assert area_of(n, nodes) is None


def test_node_on_different_layer_is_not_a_member():
    other_layer = area("layer-area", 0, 0, 1000, 1000, parent="somewhere-else")
    n = node("n1", 100, 100, parent=None)
    nodes = [other_layer, n]
    assert area_of(n, nodes) is None


def test_smallest_containing_area_wins():
    outer = area("outer", 0, 0, 2000, 2000)
    inner = area("inner", 0, 0, 500, 500)
    n = node("n1", 100, 100)  # centre (236, 220): inside both
    nodes = [outer, inner, n]
    assert area_of(n, nodes)["id"] == "inner"


def test_comment_uses_its_own_centre_offset():
    # comment centre = (x+120, y+80); place area so only the comment offset lands inside.
    a = area("a", 0, 0, 150, 100)
    c = comment("c1", 10, 10)  # centre (130, 90), inside [0,150]x[0,100]
    n = node("n1", 10, 10)  # centre (146, 130), outside [0,150]x[0,100]
    nodes = [a, c, n]
    assert area_of(c, nodes)["id"] == "a"
    assert area_of(n, nodes) is None


def test_area_never_belongs_to_another_area():
    outer = area("outer", 0, 0, 2000, 2000)
    inner = area("inner", 100, 100, 200, 200)
    nodes = [outer, inner]
    assert area_of(inner, nodes) is None


def test_area_without_size_field_is_never_a_container():
    # Defensive: a malformed area (no size) is simply skipped, not a crash.
    broken = {"id": "broken", "parentId": None, "kind": "area", "name": "", "purpose": "", "x": 0, "y": 0}
    n = node("n1", 0, 0)
    nodes = [broken, n]
    assert area_of(n, nodes) is None
