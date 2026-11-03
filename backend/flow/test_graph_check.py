from backend.flow.conftest import edge, node
from backend.flow.graph_check import graph_errors
from backend.flow.node_types import NODE_TYPES, NodeType, Port


def test_linear_graph_is_valid():
    graph = {"nodes": [node("t", "trigger.manual"), node("e", "debug.echo")], "edges": [edge("1", "t", "e")]}
    assert graph_errors(graph) == []


def test_unknown_type_duplicate_node_and_missing_port():
    graph = {"nodes": [node("t", "trigger.manual"), node("t", "debug.echo"), node("x", "nope")],
             "edges": [edge("1", "t", "ghost"), edge("2", "t", "t", source_port="approved")]}
    errors = graph_errors(graph)
    assert any("dvakrát" in e for e in errors)
    assert any("neznámý typ" in e for e in errors)
    assert any("neexistující uzel" in e for e in errors)
    assert any("nemá out port 'approved'" in e for e in errors)


def test_edge_kind_must_match_port_kinds_and_cardinality():
    registry = {**NODE_TYPES,
                "agent": NodeType("agent", 1, (Port("main", "in"), Port("model", "in", "model", "one")), None),
                "model": NodeType("model", 1, (Port("model", "out", "model"),), None)}
    nodes = [node("a", "agent"), node("m1", "model"), node("m2", "model"), node("e", "debug.echo")]
    ok = {"nodes": nodes, "edges": [edge("1", "m1", "a", "model", "model", "model")]}
    assert graph_errors(ok, registry) == []
    wrong_kind = {"nodes": nodes, "edges": [edge("1", "m1", "a", "model", "model", "main")]}
    assert any("je main, ale port m1.model je model" in e for e in graph_errors(wrong_kind, registry))
    two = {"nodes": nodes, "edges": [edge("1", "m1", "a", "model", "model", "model"),
                                     edge("2", "m2", "a", "model", "model", "model")]}
    assert any("jen jednu hranu" in e for e in graph_errors(two, registry))
    unknown = {"nodes": nodes, "edges": [edge("1", "e", "a", kind="laser")]}
    assert any("neznámý kind" in e for e in graph_errors(unknown, registry))
