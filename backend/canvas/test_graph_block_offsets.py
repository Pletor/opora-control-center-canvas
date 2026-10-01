"""Odtažené boční bloky karty: `blockOffsets` musí projít validací i uložením a načtením grafu."""

import pytest
from fastapi.testclient import TestClient
from backend.project.workspace.test_workspace_sources import ORIGIN, attach

from backend.app.factory import create_app
from backend.canvas.graph import validate_graph


def node(node_id="n1", kind="node", parent_id=None, **overrides):
    item = {
        "id": node_id,
        "parentId": parent_id,
        "kind": kind,
        "name": node_id,
        "purpose": "",
        "x": 0,
        "y": 0,
    }
    item.update(overrides)
    return item


def area(area_id="region-1", **overrides):
    return node(area_id, kind="area", size={"w": 500, "h": 500}, **overrides)


def test_node_without_block_offsets_stays_valid():
    graph = {"nodes": [node()], "edges": []}
    assert validate_graph(graph) == graph


def test_block_offsets_are_accepted_alone_and_next_to_a_source_ref():
    offsets = {"action": {"dx": 400, "dy": -120}, "material": {"dx": -300.5, "dy": 210}}
    graph = {"nodes": [node(blockOffsets=offsets)], "edges": []}
    assert validate_graph(graph) == graph
    sector = node("sector-1", kind="sector", sourceRef=None, blockOffsets={"rule": {"dx": 0, "dy": 0}})
    with_source = {"nodes": [sector], "edges": []}
    assert validate_graph(with_source) == with_source


@pytest.mark.parametrize(
    "offsets",
    [
        {"akce": {"dx": 1, "dy": 1}},
        {"action": {"dx": 1}},
        {"action": {"dx": 1, "dy": 1, "dz": 1}},
        {"action": {"dx": "x", "dy": 1}},
        {"action": {"dx": 1, "dy": 10 ** 7}},
        {"action": [1, 1]},
        [{"dx": 1, "dy": 1}],
    ],
)
def test_malformed_block_offsets_are_rejected(offsets):
    with pytest.raises(ValueError):
        validate_graph({"nodes": [node(blockOffsets=offsets)], "edges": []})


@pytest.mark.parametrize("carrier", [node("note-1", kind="comment"), area()])
def test_only_a_card_carries_block_offsets(carrier):
    carrier["blockOffsets"] = {"action": {"dx": 1, "dy": 1}}
    with pytest.raises(ValueError):
        validate_graph({"nodes": [carrier], "edges": []})


def test_block_offsets_survive_save_and_reload(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        pid = attach(client, source)
        digest = client.get("/api/view", params={"project": pid, "workspace": "draft"}).json()["digest"]
        offsets = {"action": {"dx": 512, "dy": -64}}
        graph = {"nodes": [node(blockOffsets=offsets)], "edges": []}
        saved = client.post(
            "/api/graph",
            headers={"origin": ORIGIN},
            json={"project": pid, "workspace": "draft", "graph": graph, "digest": digest},
        )
        assert saved.status_code == 200, saved.text
        reloaded = client.get("/api/view", params={"project": pid, "workspace": "draft"}).json()
        assert reloaded["graph"]["nodes"][0]["blockOffsets"] == offsets
