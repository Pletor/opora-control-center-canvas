"""Poloha nových uzlů dávky plánu: mřížka pod existujícími, bez překryvu, karta celá v oblasti."""
from backend.canvas.canvas_plan_layout import GAP, layout, overlapping


def node(nid, kind="node", parent=None, x=0, y=0, **extra):
    return {"id": nid, "parentId": parent, "kind": kind, "name": nid, "purpose": "", "x": x, "y": y, **extra}


def test_new_cards_go_below_existing_layer_without_overlap():
    existing = [node("a", x=0, y=0), node("b", x=500, y=300), node("jinde", parent="a", x=0, y=0)]
    new = [node(f"n{i}") for i in range(10)]
    assert layout(new, existing, {}) is None
    assert min(n["y"] for n in new) == 300 + 240 + GAP
    assert overlapping(existing + new) == []
    # Druhý řádek mřížky: šest karet na řádek.
    assert len({n["y"] for n in new}) == 2


def test_empty_layer_starts_at_origin_and_area_takes_its_size():
    new = [node("oblast", kind="area", size={"w": 1200, "h": 800}), node("k")]
    assert layout(new, [], {}) is None
    assert (new[0]["x"], new[0]["y"]) == (0, 0)
    # Karta mimo oblast se k ní nepřiblíží víc než na mezeru.
    assert new[1]["x"] >= 1200 + GAP or new[1]["y"] >= 800 + GAP


def test_cards_inside_area_fit_its_rectangle_or_fail():
    area = node("oblast", kind="area", x=0, y=0, size={"w": 1000, "h": 700})
    inside = [node("k1"), node("k2"), node("k3"), node("k4")]
    assert layout(inside, [area], {n["id"]: "oblast" for n in inside}) is None
    for card in inside:
        assert 0 <= card["x"] and card["x"] + 360 <= 1000
        assert 0 <= card["y"] and card["y"] + 240 <= 700
    assert overlapping([area, *inside]) == []
    extra = [node("navic")]
    assert layout(extra, [area, *inside], {"navic": "oblast"}) == "navic"
