"""Strom větví: rodič ze jména, hranice `-`, chybějící mezičlánek, platný rodič a pořadí depth-first."""
import pytest

from backend.agi_pletor.linie import tree

HEADS = {"main", "develop", "items/btn", "feat/velin", "feat/velin-linie", "feat/velin-linie-strom"}


@pytest.mark.parametrize("name, kind", [
    ("main", "main"), ("develop", "develop"), ("items/x", "items"), ("feat/x", "feat"), ("topic/x", "other"),
    ("fix/x", "fix"), ("hotfix/1", "hotfix"), ("experiment/x", "experiment"), ("feat", "other"),
])
def test_role(name, kind):
    assert tree.role(name) == kind


@pytest.mark.parametrize("name, expected", [
    ("main", None), ("develop", "main"), ("hotfix/1", "main"), ("items/btn", "develop"),
    ("feat/velin", "develop"), ("feat/velin-linie", "feat/velin"),
    ("feat/velin-linie-strom", "feat/velin-linie"), ("feat/velin-linie-x-y", "feat/velin-linie"),
    ("feat/velinzzz", "develop"), ("feat/-x", "develop"), ("fix/x", "develop"),
])
def test_parent(name, expected):
    assert tree.parent(name, HEADS) == expected


def test_parent_missing_link_and_base():
    assert tree.parent("feat/a-b-c", {"develop", "feat/a"}) == "feat/a"
    assert tree.parent("feat/a-b-c", {"develop"}) == "develop"
    assert tree.parent("fix/x", HEADS, "feat/velin") == "feat/velin"
    assert tree.parent("experiment/x", HEADS) == "develop"


def test_is_child():
    assert tree.is_child("feat/a-b", "feat/a", {"feat/a"})
    assert not tree.is_child("feat/a-b", "develop", {"feat/a"})
    assert tree.is_child("feat/a-b", "develop", set())  # mezičlánek neexistuje
    assert tree.is_child("feat/a-b-c", "feat/a", {"feat/a-b", "feat/a"})
    assert not tree.is_child("feat/velinzzz", "feat/velin", HEADS)
    assert tree.is_child("feat/a", "develop", HEADS) and not tree.is_child("feat/a", "main", HEADS)
    assert tree.is_child("items/x", "develop", HEADS) and not tree.is_child("items/x", "feat/velin", HEADS)
    assert tree.is_child("fix/x", "feat/velin", HEADS) and not tree.is_child("fix/x", "feat/nic", HEADS)


def test_depth():
    assert [tree.depth(n, HEADS) for n in ("main", "develop", "items/btn", "feat/velin", "feat/velin-linie",
                                            "feat/velin-linie-strom", "hotfix/1")] == [0, 1, 2, 2, 3, 4, 1]


def test_order_depth_first():
    heads = HEADS | {"feat/abc", "feat/velin-linie-a", "items/a", "fix/z", "chore/q", "hotfix/1"}
    assert tree.order(heads) == [
        "main", "develop", "items/a", "items/btn", "feat/abc", "feat/velin", "feat/velin-linie",
        "feat/velin-linie-a", "feat/velin-linie-strom", "chore/q", "fix/z", "hotfix/1"]


def test_may_merge():
    assert tree.may_merge("feat/velin-linie", "feat/velin", None, HEADS)
    assert not tree.may_merge("feat/velin-linie", "develop", None, HEADS)
    assert tree.may_merge("feat/velin", "develop", "develop", HEADS)
    assert tree.may_merge("items/btn", "develop", None, HEADS) and tree.may_merge("items/btn", "feat/velin", None, HEADS)
    assert not tree.may_merge("items/btn", "main", None, HEADS)
    assert tree.may_merge("fix/x", "feat/velin", "feat/velin", HEADS) and not tree.may_merge("fix/x", "main", None, HEADS)
