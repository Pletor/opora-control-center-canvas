"""Accepted graph semantics use raw values; presentation remains editable."""
import copy

import pytest

from backend.canvas.opora_graph_execution import require_accepted_graph
from backend.canvas.test_opora_changesets import SCOPE
from backend.canvas.test_opora_graph_proposals import accept, proposal
from backend.canvas.test_opora_graph_proposals import graphs as graph_fixture
from backend.canvas.test_opora_graph_proposals import service as canvas_fixture

graphs, service = graph_fixture, canvas_fixture


def check(graphs, head, graph):
    require_accepted_graph(graphs.service, *SCOPE.values(), head, graph)


@pytest.mark.parametrize("change", ["edge", "name", "purpose", "boundary"])
def test_unapproved_semantic_change_prevents_execution(graphs, service, change):
    result = accept(graphs, proposal(graphs))
    graph = copy.deepcopy(service.view("draft", "draft")["graph"])
    if change == "edge":
        graph["edges"].append({"id": "unapproved", "source": "a", "target": "b"})
    else:
        target = next(node for node in graph["nodes"] if node["id"] == ("app" if change == "boundary" else "a"))
        target["name" if change == "boundary" else change] = "Unapproved semantic change"
    with pytest.raises(ValueError, match="differs from the accepted graph"):
        check(graphs, result["id"], graph)


def test_layout_and_color_remain_allowed(graphs, service):
    result = accept(graphs, proposal(graphs))
    graph = copy.deepcopy(service.view("draft", "draft")["graph"])
    for node in graph["nodes"]:
        node.update(x=node["x"] + 50, y=node["y"] + 60, color="#445566")
    check(graphs, result["id"], graph)


def test_historical_specs_only_policy_does_not_infer_graph_approval(graphs, service):
    head = graphs.context(**SCOPE)["acceptedHead"]
    graph = copy.deepcopy(service.view("draft", "draft")["graph"])
    graph["nodes"][0]["purpose"] = "Working graph"
    check(graphs, head, graph)


def test_missing_manifest_never_falls_back_to_spec_only(graphs, service):
    result = accept(graphs, proposal(graphs))
    with service.db_for("draft") as db:
        db.execute("DELETE FROM opora_graph_manifests WHERE id=?", (result["graphManifestId"],))
    with pytest.raises(ValueError, match="does not exist"):
        check(graphs, result["id"], service.view("draft", "draft")["graph"])


def test_area_membership_is_semantic_even_when_only_coordinates_change(graphs, service):
    item = proposal(graphs, plan={"nodes": [{"ref": "area", "kind": "area", "name": "Area", "size": {"w": 1200, "h": 1000}},
                                           {"ref": "task", "kind": "node", "name": "Inside", "parent": "area"}]})
    result = accept(graphs, item)
    graph = copy.deepcopy(service.view("draft", "draft")["graph"])
    task = next(node for node in graph["nodes"] if node["id"] == item["refs"]["task"])
    task["x"] += 1
    check(graphs, result["id"], graph)
    task["x"] += 10000
    with pytest.raises(ValueError, match="accepted graph"):
        check(graphs, result["id"], graph)
