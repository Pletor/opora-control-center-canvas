"""Domain identity and relations preserve legacy graph and port semantics."""
from copy import deepcopy

import pytest

from backend.canvas.element_metadata import ELEMENT_KINDS, EDGE_RELATIONS
from backend.canvas.graph import digest, validate_graph
from backend.canvas.test_graph_carries import node


@pytest.mark.parametrize("element_kind", ELEMENT_KINDS)
@pytest.mark.parametrize("kind", ["node", "sector"])
def test_element_preserves_identity(element_kind, kind):
    item = {**node("persistent"), "kind": kind, "element": {"kind": element_kind}}
    graph = {"nodes": [item], "edges": []}
    assert validate_graph(graph) is graph
    assert item["id"] == "persistent"


@pytest.mark.parametrize("element", [None, {}, {"kind": "task"}, {"kind": "service", "id": "other"}, {"kind": []}])
def test_invalid_element(element):
    with pytest.raises(ValueError, match="element"):
        validate_graph({"nodes": [{**node("a"), "element": element}], "edges": []})


def test_comment_cannot_own_application_role():
    with pytest.raises(ValueError, match="element"):
        validate_graph({"nodes": [{**node("a"), "kind": "comment", "element": {"kind": "service"}}], "edges": []})


@pytest.mark.parametrize("relation", EDGE_RELATIONS)
@pytest.mark.parametrize("port", [None, "next", "rule", "action", "block"])
def test_relation_independent_of_port(relation, port):
    edge = {"id": "e", "source": "a", "target": "b", "relation": relation, "reason": "Accepted input"}
    if port:
        edge["port"] = port
    if port == "block":
        edge.update(sourceBlockId="block", sourcePortId="output")
    graph = {"nodes": [node("a"), node("b")], "edges": [edge]}
    assert validate_graph(graph) == graph


@pytest.mark.parametrize("fields", [{"relation": "contains"}, {"relation": None}, {"relation": []}, {"reason": "missing relation"}, {"relation": "uses", "reason": " "}, {"relation": "uses", "reason": "x" * 1001}])
def test_invalid_relation(fields):
    with pytest.raises(ValueError):
        validate_graph({"nodes": [node("a"), node("b")], "edges": [{"id": "e", "source": "a", "target": "b", **fields}]})


def test_only_blocking_dependency_cycles_are_rejected():
    graph = {"nodes": [node("a"), node("b"), node("c")], "edges": [
        {"id": "ab", "source": "a", "target": "b", "relation": "requires"},
        {"id": "bc", "source": "b", "target": "c", "relation": "requires"},
        {"id": "ca", "source": "c", "target": "a", "relation": "uses"},
    ]}
    validate_graph(graph)
    graph["edges"][2]["relation"] = "requires"
    with pytest.raises(ValueError, match="cyklus"):
        validate_graph(graph)


def test_legacy_graph_is_not_rewritten():
    graph = {"nodes": [node("a"), node("b")], "edges": [{"id": "ab", "source": "a", "target": "b", "carries": "data"}]}
    before, fingerprint = deepcopy(graph), digest(graph)
    validate_graph(graph)
    assert graph == before and digest(graph) == fingerprint


@pytest.mark.parametrize("readiness", ["design", "implemented", "verified"])
def test_parent_requirement_cannot_target_its_own_descendant(readiness):
    graph = {"nodes": [{**node("sector"), "kind": "sector"}, {**node("child"), "parentId": "sector"}], "edges": [
        {"id": "input", "source": "sector", "target": "child", "relation": "requires",
         "requirement": {"readiness": readiness, "revision": 0}}]}
    with pytest.raises(ValueError, match="cyklus"):
        validate_graph(graph)


def test_cycle_through_inherited_requirement_is_rejected():
    graph = {"nodes": [{**node("sector"), "kind": "sector"}, {**node("child"), "parentId": "sector"}, node("external")], "edges": [
        {"id": "input", "source": "sector", "target": "external", "relation": "requires"},
        {"id": "back", "source": "external", "target": "child", "relation": "requires"}]}
    with pytest.raises(ValueError, match="cyklus"):
        validate_graph(graph)
    graph["edges"].pop()
    assert validate_graph(graph) is graph  # Ordinary ancestor requirement on an external input is valid.


def test_collaboration_with_descendant_does_not_become_inherited_blocking_cycle():
    graph = {"nodes": [{**node("sector"), "kind": "sector"}, {**node("child"), "parentId": "sector"}], "edges": [
        {"id": "a", "source": "sector", "target": "child", "relation": "uses"},
        {"id": "b", "source": "child", "target": "sector", "relation": "communicates_with"}]}
    assert validate_graph(graph) is graph


@pytest.mark.parametrize("requirement", [None, {}, {"readiness": "done", "revision": 1},
    {"readiness": "design", "revision": -1}, {"readiness": "design", "revision": True},
    {"readiness": "verified", "revision": 1, "verification": {}}])
def test_invalid_required_input_is_rejected(requirement):
    with pytest.raises(ValueError):
        validate_graph({"nodes": [node("a"), node("b")], "edges": [
            {"id": "e", "source": "a", "target": "b", "relation": "requires", "requirement": requirement}]})


def test_readiness_descriptor_belongs_only_to_blocking_dependency():
    with pytest.raises(ValueError, match="requirement"):
        validate_graph({"nodes": [node("a"), node("b")], "edges": [
            {"id": "e", "source": "a", "target": "b", "relation": "uses", "requirement": {"readiness": "design", "revision": 0}}]})


def test_dependency_validation_handles_full_graph_without_recursion():
    graph = {"nodes": [node(str(i)) for i in range(2000)], "edges": [
        {"id": str(i), "source": str(i), "target": str(i + 1), "relation": "requires"}
        for i in range(1999)
    ]}
    validate_graph(graph)
    graph["edges"].append({"id": "cycle", "source": "1999", "target": "0", "relation": "requires"})
    with pytest.raises(ValueError, match="cyklus"):
        validate_graph(graph)
