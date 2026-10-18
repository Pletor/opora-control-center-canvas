"""Poloha nových uzlů dávky plánu: mřížka pod existujícími, bez překryvu, karta celá v pružné oblasti."""
from backend.canvas.canvas_plan_layout import AREA_PAD, CARD, GAP, layout, overlapping


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


def inside_area(card, area):
    ax, ay, aw, ah = area["x"], area["y"], area["size"]["w"], area["size"]["h"]
    return ax <= card["x"] and card["x"] + CARD[0] <= ax + aw and ay <= card["y"] and card["y"] + CARD[1] <= ay + ah


def test_cards_inside_area_fit_its_rectangle():
    area = node("oblast", kind="area", x=0, y=0, size={"w": 1000, "h": 700})
    inside = [node("k1"), node("k2"), node("k3"), node("k4")]
    assert layout(inside, [area], {n["id"]: "oblast" for n in inside}) is None
    assert area["size"] == {"w": 1000, "h": 700}
    for card in inside:
        assert inside_area(card, area)
    assert overlapping([area, *inside]) == []


def test_full_area_grows_by_columns_then_rows():
    area = node("oblast", kind="area", x=0, y=0, size={"w": 1000, "h": 700})
    inside = [node("k1"), node("k2"), node("k3"), node("k4")]
    assert layout(inside, [area], {n["id"]: "oblast" for n in inside}) is None
    # Pátá karta: dva sloupce jsou plné, rámeček vyroste na tři sloupce.
    fifth = node("k5")
    assert layout([fifth], [area, *inside], {"k5": "oblast"}) is None
    assert area["size"] == {"w": 2 * AREA_PAD + 3 * CARD[0] + 2 * GAP, "h": 700}
    assert inside_area(fifth, area)
    # Sedmá karta: tři sloupce po dvou řádcích jsou plné, rámeček přidá řádek.
    sixth, seventh = node("k6"), node("k7")
    assert layout([sixth, seventh], [area, *inside, fifth], {"k6": "oblast", "k7": "oblast"}) is None
    assert area["size"] == {"w": 2 * AREA_PAD + 3 * CARD[0] + 2 * GAP, "h": 700 + CARD[1] + GAP}
    assert inside_area(seventh, area)
    assert overlapping([area, *inside, fifth, sixth, seventh]) == []


def test_area_hemmed_in_by_neighbours_cannot_grow_and_fails():
    area = node("oblast", kind="area", x=0, y=0, size={"w": 600, "h": 400})
    right = node("vpravo", x=600 + GAP, y=0)
    below = node("dole", x=0, y=400 + GAP)
    first = node("k1")
    assert layout([first], [area, right, below], {"k1": "oblast"}) is None
    extra = node("navic")
    assert layout([extra], [area, right, below, first], {"navic": "oblast"}) == "navic"
    assert area["size"] == {"w": 600, "h": 400}
