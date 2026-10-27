"""Druh toku vazby `carries` (`docs/architektura-pro-agenty.md` §3.4): nepovinný, jen u vazby `next`
nebo bez portu, nikdy se nedoplňuje. Vazby bez něj zůstávají bajt po bajtu stejné."""
import pytest

from backend.canvas.graph import EDGE_CARRIES, digest, validate_graph


def node(node_id):
    return {"id": node_id, "parentId": None, "kind": "node", "name": node_id, "purpose": "", "x": 0, "y": 0}


def graph(edge):
    return {"nodes": [node("a"), node("b")], "edges": [edge]}


@pytest.mark.parametrize("carries", EDGE_CARRIES)
@pytest.mark.parametrize("port", [{}, {"port": "next"}])
def test_next_edge_accepts_each_carries(carries, port):
    edge = {"id": "e1", "source": "a", "target": "b", **port, "carries": carries}
    assert validate_graph(graph(edge))["edges"][0] == edge


@pytest.mark.parametrize("carries", ["flow", "", None, "Navigation", ["data"]])
def test_unknown_carries_is_rejected(carries):
    with pytest.raises(ValueError, match="carries"):
        validate_graph(graph({"id": "e1", "source": "a", "target": "b", "carries": carries}))


@pytest.mark.parametrize("port", ["flow", "rule", "action"])
def test_other_ports_reject_carries(port):
    with pytest.raises(ValueError, match="jen vazba next"):
        validate_graph(graph({"id": "e1", "source": "a", "target": "b", "port": port, "carries": "data"}))


def test_block_port_rejects_carries():
    edge = {"id": "e1", "source": "a", "target": "b", "port": "block", "sourceBlockId": "b1",
            "sourcePortId": "p1", "carries": "command"}
    with pytest.raises(ValueError):
        validate_graph(graph(edge))


def test_edge_without_carries_is_unchanged_and_keeps_digest():
    edge = {"id": "e1", "source": "a", "target": "b", "port": "next"}
    before = digest(graph(dict(edge)))
    validated = validate_graph(graph(dict(edge)))
    assert "carries" not in validated["edges"][0]
    assert digest(validated) == before
