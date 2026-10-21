"""Pure selector closure, negative predicates, and actual-reader equivalence."""

import copy

import pytest

from backend.editor.agent_packet.sector_status import sector_blockers
from backend.editor.agent_packet.specification_context import _node
from backend.editor.agent_packet.specification_scope import project_graph, select_scope


def node(identifier, parent=None, kind="node", **fields):
    return {"id": identifier, "parentId": parent, "kind": kind, "name": identifier,
            "x": 0, "y": 0, **fields}


def edge(identifier, source, target, **fields):
    return {"id": identifier, "source": source, "target": target, **fields}


def graph(nodes, edges=()):
    return {"nodes": nodes, "edges": list(edges)}


def fixture():
    return graph([
        node("root", kind="sector"), node("target-sector", "root", "sector"),
        node("target", "target-sector"), node("child", "target"),
        node("endpoint-parent", kind="sector"), node("endpoint", "endpoint-parent"),
        node("unrelated"), node("prior", kind="sector", gateNodeId="gate"),
        node("nested", "prior", "sector"), node("prior-child", "nested"),
        node("gate", "prior", scenario={"command": "check"}),
    ], [edge("incident", "child", "endpoint"),
        edge("excluded", "endpoint", "unrelated"), edge("gate-edge", "prior", "root")])


def test_exact_closure_has_ancestors_members_and_no_component_expansion():
    value = fixture()
    selection = select_scope(value, "target")
    assert selection["edgeIds"] == ["gate-edge", "incident"]
    assert set(selection["cardIds"]) == {n["id"] for n in value["nodes"]} - {
        "unrelated", "nested", "prior-child", "gate"}
    assert selection["gatingIds"] == ["gate", "prior", "prior-child", "target"]
    before = copy.deepcopy(selection)
    value["nodes"][-5]["name"] = "Unrelated content changes"
    value["edges"].append(edge("irrelevant-flow", "unrelated", "root", port="flow"))
    assert select_scope(value, "target") == before
    value["nodes"].reverse()
    value["edges"].reverse()
    assert select_scope(value, "target") == before


def test_negative_selectors_and_relevant_additions():
    value = graph([node("parent", kind="sector"), node("target", "parent"), node("other")])
    base = select_scope(value, "target")
    assert {"type": "descendants", "nodeId": "target", "nodeIds": []} in base["predicates"]
    assert {"type": "incoming-next", "nodeId": "parent", "edgeIds": []} in base["predicates"]
    value["edges"].append(edge("incoming", "other", "parent"))
    assert select_scope(value, "target") != base
    assert select_scope(value, "target")["gatingIds"] == ["other", "target"]
    value["nodes"].append(node("child", "target"))
    assert "child" in select_scope(value, "target")["cardIds"]
    value["edges"].append(edge("incident", "target", "other", port="flow"))
    assert "incident" in select_scope(value, "target")["edgeIds"]


def test_predecessor_null_gate_new_member_and_gate_change_selection():
    value = fixture()
    del value["nodes"][7]["gateNodeId"]
    base = select_scope(value, "target")
    assert {"type": "gate", "nodeId": "prior", "gateNodeId": None} in base["predicates"]
    value["nodes"].append(node("new", "nested"))
    assert select_scope(value, "target") != base
    value["nodes"][7]["gateNodeId"] = "other-gate"
    value["nodes"].append(node("other-gate"))
    assert "other-gate" in select_scope(value, "target")["gatingIds"]


@pytest.mark.parametrize("gate,complete,scenario", [(False, False, False), (False, True, False),
                                                   (True, True, False), (True, True, True)])
def test_blockers_match_full_graph_with_same_state(gate, complete, scenario):
    value = fixture()
    if not gate:
        del value["nodes"][7]["gateNodeId"]
    state = {"nodes": {identifier: {"done": {"confirmed": complete, "by": "human"}}
                       for identifier in ("gate", "prior-child")}}
    if scenario:
        state["nodes"]["gate"]["scenarioRun"] = {"command": "check", "failed": 0}
    projected = project_graph(value, select_scope(value, "target"))["graph"]
    assert sector_blockers(projected, state, "target") == sector_blockers(value, state, "target")


def test_full_source_area_winner_and_graph_only_geometry():
    value = graph([node("target"), node("big", kind="area", size={"w": 900, "h": 900}),
                   node("small", kind="area", size={"w": 400, "h": 300}), node("unrelated")])
    selection = select_scope(value, "target")
    assert selection["cardIds"] == ["target"]
    assert selection["nodeIds"] == ["small", "target"]
    projected = project_graph(value, selection)["graph"]
    target = next(item for item in projected["nodes"] if item["id"] == "target")
    assert target == _node(value["nodes"][0], value["nodes"])
    assert target["areaId"] == "small"
    value["nodes"][2]["x"] = 1000
    assert select_scope(value, "target") != selection
    with pytest.raises(ValueError, match="Stale"):
        project_graph(value, selection)


def test_navigation_relevant_domain_all_pages_original_order_graph_only():
    value = graph([node("app", kind="sector", site={"kind": "application"}),
                   node("target", "app"), node("z-page", "app", site={"kind": "page"}),
                   node("container", "app", "sector"),
                   node("a-page", "container", site={"kind": "page"}),
                   node("other-app", kind="sector", site={"kind": "application"}),
                   node("other-page", "other-app", site={"kind": "page"})])
    selection = select_scope(value, "target")
    assert selection["cardIds"] == ["app", "target"]
    assert selection["nodeIds"] == ["a-page", "app", "container", "target", "z-page"]
    assert project_graph(value, selection)["navigation"] == [{"domainId": "app", "pages": [
        {"nodeId": "z-page", "parentPageId": None},
        {"nodeId": "a-page", "parentPageId": None}]}]
    value["nodes"][2], value["nodes"][4] = value["nodes"][4], value["nodes"][2]
    assert select_scope(value, "target") != selection


@pytest.mark.parametrize("value", [graph([node("target"), node("target")]),
    graph([node("target", "missing")]), graph([node("target", "loop"), node("loop", "target")]),
    graph([node("target")], [edge("broken", "target", "missing")]),
    graph([node("target"), node("prior", kind="sector", gateNodeId="missing")],
          [edge("gate", "prior", "target")]),
    graph([node("target")], [edge("same", "target", "target")] * 2),
    graph([node("target"), *[node(str(i)) for i in range(2000)]]),
    graph([node("target")], [edge(str(i), "target", "target") for i in range(8001)])])
def test_malformed_or_unbounded_graph_fails_closed(value):
    # A gating target must be a sector for the missing gate to be an actual read.
    if len(value["nodes"]) == 2 and value["nodes"][1].get("gateNodeId"):
        value["nodes"][0]["kind"] = "sector"
    with pytest.raises(ValueError):
        select_scope(value, "target")


def test_raw_projection_preserves_values_hidden_by_public_redaction():
    value = graph([node("target", purpose="token=abcdefgh12345678")])
    selection = select_scope(value, "target")
    first = project_graph(value, selection, redact=False)
    first_public = project_graph(value, selection)
    value["nodes"][0]["purpose"] = "token=ijklmnop87654321"
    second = project_graph(value, selection, redact=False)
    assert first != second
    assert first_public == project_graph(value, selection)
    assert "purpose" not in str(selection)


def test_deep_descendants_and_endpoint_ancestors_without_sibling_content():
    value = graph([node("target-root", kind="sector"), node("target", "target-root"),
                   node("one", "target"), node("two", "one"), node("three", "two"),
                   node("far-root", kind="sector"), node("far-parent", "far-root", "sector"),
                   node("far", "far-parent"), node("sibling", "far-parent"), node("other")],
                  [edge("deep", "three", "far"), edge("far-edge", "far", "other")])
    selection = select_scope(value, "target")
    assert set(selection["cardIds"]) == {item["id"] for item in value["nodes"]} - {
        "sibling", "other"}
    assert selection["edgeIds"] == ["deep"]
    value["nodes"].append(node("sibling-child", "sibling"))
    assert select_scope(value, "target") == selection


def test_source_card_legacy_next_state_and_non_next_exclusion():
    value = graph([node("sector", kind="sector"), node("target", "sector"),
                   node("prior"), node("flow-source")],
                  [edge("legacy", "prior", "sector"),
                   edge("flow", "flow-source", "sector", port="flow")])
    selection = select_scope(value, "target")
    assert selection["gatingIds"] == ["prior", "target"]
    assert "flow-source" not in selection["nodeIds"]
    projected = project_graph(value, selection)["graph"]
    for done in (False, True):
        state = {"nodes": {"prior": {"done": {"confirmed": done}}}}
        assert sector_blockers(projected, state, "target") == sector_blockers(
            value, state, "target")


def test_predecessor_members_and_gate_do_not_claim_card_content_reads():
    value = fixture()
    selection = select_scope(value, "target")
    for identifier in ("prior-child", "gate"):
        assert identifier in selection["nodeIds"]
        assert identifier in selection["gatingIds"]
        assert identifier not in selection["cardIds"]
    # A caller must capture specs/text/drawings only for cardIds, never gatingIds.
    value["edges"].append(edge("direct", "target", "gate"))
    assert "gate" in select_scope(value, "target")["cardIds"]


def test_far_area_does_not_change_selection_but_containing_area_does():
    value = graph([node("target")])
    selection = select_scope(value, "target")
    value["nodes"].append(node("far", kind="area", x=10000, size={"w": 400, "h": 300}))
    assert select_scope(value, "target") == selection
    value["nodes"].append(node("near", kind="area", size={"w": 400, "h": 300}))
    assert select_scope(value, "target") != selection
