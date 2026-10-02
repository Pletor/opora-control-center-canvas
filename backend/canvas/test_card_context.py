"""Kontext karty: efektivní druh a stav, slug a čitelná adresa (kontrakt §1 a §3)."""

import pytest

from backend.canvas.card_context import (
    card_address,
    card_layer,
    card_path,
    effective_status,
    effective_type,
    fold,
    slug,
)


def node(node_id, name, parent_id=None, **extra):
    return {"id": node_id, "parentId": parent_id, "kind": "node", "name": name, **extra}


@pytest.mark.parametrize(
    "name, expected",
    [
        ("[research] Trh", "research"),
        ("[prototype] Náčrt", "prototype"),
        ("[grilling] Otázky", "grilling"),
        ("[task] Router", "task"),
        ("[Task] Router", None),
        ("[task]Router", None),
        (" [task] Router", None),
        ("[bug] Router", None),
        ("Router [task] ", None),
        ("Router", None),
    ],
)
def test_effective_type_reads_exact_prefix(name, expected):
    assert effective_type(node("n1", name)) == expected


def test_type_comes_only_from_prefix_and_layer_from_card():
    assert effective_type(node("n1", "[task] Router", card={"layer": "backend"})) == "task"
    assert effective_type(node("n1", "Router", card={"status": "ready"})) is None
    assert card_layer(node("n1", "Router", card={"layer": "backend"})) == "backend"
    assert card_layer(node("n1", "Router", card={"layer": "fe"})) is None
    assert card_layer(node("n1", "Router")) is None


def test_effective_status():
    assert effective_status(node("n1", "A"), False) is None
    assert effective_status(node("n1", "A", card={"status": "draft"}), False) == "draft"
    assert effective_status(node("n1", "A", card={"status": "ready"}), True) == "done"
    assert effective_status(node("n1", "A"), True) == "done"


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Pop-up tvorby", "pop-up-tvorby"),
        ("Žluťoučký kůň", "zlutoucky-kun"),
        ("[task] Router API", "router-api"),
        ("  --Editor!!  ", "editor"),
        ("A__B  C", "a-b-c"),
        ("!!!", "n1"),
        ("", "n1"),
        ("[task] ", "n1"),
    ],
)
def test_slug(name, expected):
    assert slug(name, "n1") == expected


def test_fold_removes_diacritics_and_case():
    assert fold("ŘÍZENÍ Úloh") == "rizeni uloh"


def test_path_and_address_go_from_root_to_card():
    nodes = [
        {"id": "s1", "parentId": None, "kind": "sector", "name": "Editor"},
        node("n1", "[task] Pop-up tvorby", "s1"),
    ]
    by_id = {item["id"]: item for item in nodes}
    assert card_path(by_id, by_id["n1"]) == ["Editor", "[task] Pop-up tvorby"]
    assert card_address(by_id, by_id["n1"]) == "editor/pop-up-tvorby"
    assert card_address(by_id, by_id["s1"]) == "editor"


def test_address_survives_missing_parent_and_cycle():
    lonely = node("n1", "Sám", "zmizel")
    assert card_address({"n1": lonely}, lonely) == "sam"
    a, b = node("a", "A", "b"), node("b", "B", "a")
    assert card_address({"a": a, "b": b}, a) == "b/a"
