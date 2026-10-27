"""Druh toku `carries` v návrzích a změnách grafu OporaHub: nastavení i odebrání je viditelná změna vazby,
úprava bez `carries` odvodí stejná pole jako dřív a vazbu s `carries` lze přidat jen jako `next`."""
from copy import deepcopy

import pytest

from backend.canvas.opora_graph_build import validate_plan
from backend.canvas.opora_graph_change_build import build
from backend.canvas.test_opora_graph_change_build import graph

REWIRE = {"id": "edge", "source": "child", "target": "other", "port": "next"}


def test_setting_carries_shows_as_edge_change_with_its_field():
    result = build(graph(), graph(), {"updateEdges": [{**REWIRE, "carries": "command"}]}, {})
    assert result["resultGraph"]["edges"][0]["carries"] == "command"
    [change] = result["changes"]["edges"]
    assert (change["operation"], change["fields"]) == ("update", ["source", "target", "port", "carries"])
    assert "carries" not in change["workingBefore"] and change["proposedWorking"]["carries"] == "command"
    assert result["preconditions"]["working"]["edges"]["edge"]["carries"] == {"present": False, "value": None}


def test_null_carries_removes_it():
    with_carries = graph()
    with_carries["edges"][0]["carries"] = "data"
    result = build(with_carries, with_carries, {"updateEdges": [{**REWIRE, "carries": None}]}, {})
    assert "carries" not in result["resultGraph"]["edges"][0]


def test_rewire_without_carries_keeps_carries_and_old_fields():
    with_carries = graph()
    with_carries["nodes"].append(deepcopy(with_carries["nodes"][2]) | {"id": "third", "name": "third"})
    with_carries["edges"][0]["carries"] = "navigation"
    result = build(with_carries, with_carries, {"updateEdges": [{**REWIRE, "target": "third"}]}, {})
    assert result["resultGraph"]["edges"][0] == {**REWIRE, "target": "third", "carries": "navigation"}
    assert result["changes"]["edges"][0]["fields"] == ["source", "target", "port"]
    assert set(result["preconditions"]["working"]["edges"]["edge"]) == {"source", "target", "port"}


@pytest.mark.parametrize("value", ["stream", "", 1])
def test_unknown_carries_update_is_rejected(value):
    with pytest.raises(ValueError, match="carries"):
        build(graph(), graph(), {"updateEdges": [{**REWIRE, "carries": value}]}, {})


def test_added_edge_may_carry_only_on_next():
    validate_plan({"edges": [{"from": "@a", "to": "@b", "carries": "event"}]})
    with pytest.raises(ValueError):
        validate_plan({"edges": [{"from": "@a", "to": "@b", "port": "rule", "carries": "event"}]})
