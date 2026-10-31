"""Zápis srdce do architektury smí měnit jen `order` existujících uzlů a jen při plné autonomii projektu."""
import pytest

from backend.canvas.architecture_order import (
    HeartArchitectureRefused,
    other_changes,
    require_autonomy,
    require_order_only,
)

OLD = {"nodes": [{"id": "app", "kind": "sector", "name": "App"}, {"id": "home", "kind": "node", "name": "Domů", "order": 3}],
       "edges": [{"id": "e1", "source": "app", "target": "home", "port": "next"}]}


def with_nodes(*nodes):
    return {**OLD, "nodes": list(nodes)}


def test_order_alone_may_change_be_added_or_removed():
    assert other_changes(OLD, with_nodes({**OLD["nodes"][0], "order": 101}, {"id": "home", "kind": "node", "name": "Domů"})) == []
    require_order_only(OLD, OLD)


@pytest.mark.parametrize(("new", "expected"), [
    (with_nodes(OLD["nodes"][0], {**OLD["nodes"][1], "name": "Jinak"}), ["home"]),
    (with_nodes(OLD["nodes"][0]), ["uzly"]),
    (with_nodes(OLD["nodes"][1], OLD["nodes"][0]), ["uzly"]),
    (with_nodes(*OLD["nodes"], {"id": "faq", "kind": "node", "name": "FAQ"}), ["uzly"]),
    ({**OLD, "edges": []}, ["vazby"]),
])
def test_anything_else_is_refused_422(new, expected):
    assert other_changes(OLD, new) == expected
    with pytest.raises(HeartArchitectureRefused) as refused:
        require_order_only(OLD, new)
    assert (refused.value.status, refused.value.code) == (422, "heart_architecture_scope")


def test_without_full_autonomy_the_write_is_refused_403():
    require_autonomy(True)
    with pytest.raises(HeartArchitectureRefused) as refused:
        require_autonomy(False)
    assert (refused.value.status, refused.value.body()["code"]) == (403, "heart_architecture_autonomy")
