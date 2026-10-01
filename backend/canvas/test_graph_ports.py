"""Porty vazby: volitelné `port` (next/action/rule/block); staré vazby bez portu zůstávají platné.

`port: "block"` je tlačítko bloku a nese navíc `sourceBlockId` a `sourcePortId`; ty dvě pole
nesmí být nikde jinde.
"""
import pytest

from backend.canvas.graph import validate_graph


def node(node_id):
    return {"id": node_id, "parentId": None, "kind": "node", "name": node_id, "purpose": "", "x": 0, "y": 0}


def graph(edge):
    return {"nodes": [node("a"), node("b")], "edges": [edge]}


def test_legacy_edge_without_port_is_accepted_unchanged():
    edge = {"id": "e1", "source": "a", "target": "b"}
    assert validate_graph(graph(edge))["edges"][0] == edge


@pytest.mark.parametrize("port", ["next", "action", "rule"])
def test_edge_with_known_port_is_accepted(port):
    edge = {"id": "e1", "source": "a", "target": "b", "port": port}
    assert validate_graph(graph(edge))["edges"][0]["port"] == port


@pytest.mark.parametrize(
    "edge",
    [
        {"id": "e1", "source": "a", "target": "b", "port": "pipeline"},
        {"id": "e1", "source": "a", "target": "b", "port": ""},
        {"id": "e1", "source": "a", "target": "b", "port": None},
        {"id": "e1", "source": "a", "target": "b", "port": "next", "extra": 1},
        {"id": "e1", "source": "a", "target": "b", "blockId": "x"},
    ],
)
def test_unknown_port_or_extra_keys_are_rejected(edge):
    with pytest.raises(ValueError):
        validate_graph(graph(edge))


def block_edge(**overrides):
    edge = {"id": "e1", "source": "a", "target": "b", "port": "block",
            "sourceBlockId": "b1", "sourcePortId": "p1"}
    edge.update(overrides)
    return edge


def test_block_port_edge_carries_source_block_and_port():
    edge = block_edge()
    assert validate_graph(graph(edge))["edges"][0] == edge


@pytest.mark.parametrize(
    "edge",
    [
        # port `block` bez bloku nebo bez portu je půlka zápisu
        {"id": "e1", "source": "a", "target": "b", "port": "block"},
        {"id": "e1", "source": "a", "target": "b", "port": "block", "sourceBlockId": "b1"},
        {"id": "e1", "source": "a", "target": "b", "port": "block", "sourcePortId": "p1"},
        # blok a port zdroje u jiného portu (nebo bez portu) nemají co dělat
        block_edge(port="next"),
        block_edge(port="action"),
        {"id": "e1", "source": "a", "target": "b", "sourceBlockId": "b1", "sourcePortId": "p1"},
        # neplatné identifikátory bloku nebo portu
        block_edge(sourceBlockId=""),
        block_edge(sourcePortId=""),
        block_edge(sourceBlockId="ne platné!"),
        block_edge(sourcePortId=None),
        block_edge(sourceBlockId="x" * 81),
        block_edge(extra=1),
    ],
)
def test_block_port_edge_without_both_keys_or_with_bad_ids_is_rejected(edge):
    with pytest.raises(ValueError):
        validate_graph(graph(edge))
