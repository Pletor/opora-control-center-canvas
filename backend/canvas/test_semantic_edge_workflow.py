"""A semantic relation never inherits the legacy visual-port work ordering."""
import pytest

from backend.canvas.card_dag import next_edges
from backend.canvas.test_graph_card import node
from backend.editor.agent_packet.sector_status import sector_blockers
from backend.editor.agent_packet.specification_scope import select_scope
from backend.brain_opora.determinism.ticket_model import neighbors


@pytest.mark.parametrize("relation", ["requires", "uses", "communicates_with", "evidences"])
@pytest.mark.parametrize("port", [{}, {"port": "next"}])
def test_semantic_ports_do_not_add_predecessors_or_followup_tasks(relation, port):
    edge = {"id": "semantic", "source": "a", "target": "b", "relation": relation, **port}
    graph = {"nodes": [{**node("a"), "kind": "sector"}, {**node("b"), "kind": "sector"}, node("work", parent_id="b")], "edges": [edge]}
    assert next_edges(graph) == []
    assert sector_blockers(graph, {"nodes": {}}, "work") == []
    assert neighbors(graph, "a") == {"successors": [], "predecessors": []}
    selection = select_scope(graph, "work")
    assert all(not predicate["edgeIds"] for predicate in selection["predicates"] if predicate["type"] == "incoming-next")
    legacy = {**graph, "edges": [{key: value for key, value in edge.items() if key != "relation"}]}
    assert next_edges(legacy) == [("a", "b")]
    assert sector_blockers(legacy, {"nodes": {}}, "work")
    assert neighbors(legacy, "a")["successors"][0]["cardId"] == "b"


@pytest.mark.parametrize("relation", ["uses", "communicates_with"])
def test_collaboration_cycles_at_next_port_are_not_workflow_cycles(relation):
    from backend.canvas.card_dag import CardCycleError, check_save
    from backend.canvas.graph import validate_graph
    graph = {"nodes": [node("a"), node("b")], "edges": [
        {"id": "ab", "source": "a", "target": "b", "port": "next", "relation": relation},
        {"id": "ba", "source": "b", "target": "a", "relation": relation},
    ]}
    validate_graph(graph)
    check_save(None, graph)
    for edge in graph["edges"]:
        edge["relation"] = "requires"
    with pytest.raises(ValueError, match="cyklus"):
        validate_graph(graph)
    for edge in graph["edges"]:
        edge.pop("relation")
    with pytest.raises(CardCycleError):
        check_save(None, graph)
