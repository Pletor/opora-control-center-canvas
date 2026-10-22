"""Card DAG: `next` cycles are rejected on save (409 with the path), blockedBy/topoIndex reach agent-state."""
import json

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas import card_dag
from backend.canvas import opora_agent_state_pulls as pulls
from backend.canvas.opora_agent_state import AgentState
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.test_opora_changesets import SCOPE, baseline, legacy_save
from backend.canvas.test_opora_changesets import service as service  # noqa: PLC0414
from backend.canvas.test_opora_process_sync import route
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State


@pytest.fixture(autouse=True)
def no_pull_module():
    pulls.register(None)
    original = pulls.source
    pulls.source = lambda: pulls._override
    yield
    pulls.source = original
    pulls.register(None)


def edge(identifier, source, target, port=None):
    value = {"id": identifier, "source": source, "target": target}
    return value if port is None else {**value, "port": port}


def save_edges(service, *edges):
    current = service.view("draft", "draft")
    graph = {"nodes": current["graph"]["nodes"], "edges": list(edges)}
    return service.save_graph("draft", "draft", graph, current["digest"])


def test_next_cycle_is_rejected_with_its_path(service):
    save_edges(service, edge("e1", "a", "b"))
    with pytest.raises(card_dag.CardCycleError) as error:
        save_edges(service, edge("e1", "a", "b"), edge("e2", "b", "a"))
    assert error.value.cycle == ["b", "a", "b"]
    # Other ports are not `next` and never form a card cycle.
    save_edges(service, edge("e1", "a", "b"), edge("e2", "b", "a", "action"))


def test_graph_route_answers_409_with_the_cycle(service):
    save_edges(service, edge("e1", "a", "b"))
    current = service.view("draft", "draft")
    graph = {"nodes": current["graph"]["nodes"], "edges": [edge("e1", "a", "b"), edge("e2", "b", "a", "next")]}
    with TestClient(create_app(service.root), base_url="http://127.0.0.1:8740") as client:
        response = client.post("/api/graph", json={**SCOPE, "graph": graph, "digest": current["digest"]},
                               headers={"Origin": "http://127.0.0.1:8740"})
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "card_cycle" and response.json()["cycle"] == ["b", "a", "b"]


def test_legacy_cycle_is_tolerated_but_a_new_one_is_not():
    cards = {"nodes": [{"id": key, "kind": "node"} for key in "abc"], "edges": []}
    legacy = {**cards, "edges": [edge("1", "a", "b"), edge("2", "b", "a")]}
    assert card_dag.introduced_cycle(legacy, legacy) is None
    grown = {**cards, "edges": [*legacy["edges"], edge("3", "b", "c"), edge("4", "c", "b")]}
    assert card_dag.introduced_cycle(legacy, grown) == ["b", "c", "b"]
    assert card_dag.topo_order("abc", card_dag.next_edges(legacy)) == ["c", "a", "b"]


def test_topo_order_and_blocked_by_are_deterministic():
    pairs = [("a", "c"), ("b", "c"), ("c", "d")]
    assert card_dag.topo_order("dcba", pairs) == ["a", "b", "c", "d"]
    assert card_dag.blocked_by("abcd", pairs, {"a"}) == {"a": [], "b": [], "c": ["b"], "d": ["c"]}


@pytest.fixture
def chained(service):
    """Card `b` precedes card `a`; `a` has an accepted goal and a pipeline, so its claim would be ready."""
    save_edges(service, edge("e1", "b", "a"))
    legacy_save(service, goal="Read accepted task")
    baseline(service)
    route(service)
    return ExecutionResults(service)


def card(document, node):
    return next(item for item in document["cards"] if item["nodeId"] == node)


def test_unfinished_predecessor_blocks_the_claim(chained, service):
    document = AgentState(service).read(**SCOPE)
    [action] = [item for item in document["actions"] if item["verb"] == "claim"]
    assert action["status"] == "blocked" and action["blockReason"] == "blocked_by_predecessor"
    entry = card(document, "a")
    assert entry["blockedBy"] == ["b"] and entry["nextActionId"] == action["id"]
    assert entry["stage"] == "claim" and entry["reason"] == "blocked_by_predecessor"
    assert card(document, "b")["topoIndex"] < entry["topoIndex"]
    assert {"kind", "layer", "gate"} <= set(entry) and entry["gate"] is None
    assert next(item for item in document["stages"] if item["id"] == "claim")["reason"] == "nothing_ready"


def test_merged_and_written_back_predecessor_unblocks(chained, service):
    blocked = AgentState(service).read(**SCOPE)
    pulls.register(lambda p, w: [{"executionId": "x1", "cardId": "b", "state": "merged", "planWrittenBack": True}])
    document = AgentState(service).read(**SCOPE)
    [action] = [item for item in document["actions"] if item["verb"] == "claim"]
    assert action["status"] == "ready" and card(document, "a")["blockedBy"] == []
    old = next(item for item in blocked["actions"] if item["verb"] == "claim")
    assert old["id"] != action["id"]  # A changed blocker set is a new intent.
    pulls.register(lambda p, w: [{"executionId": "x1", "cardId": "b", "state": "merged", "planWrittenBack": False}])
    assert card(AgentState(service).read(**SCOPE), "a")["blockedBy"] == ["b"]


def test_legacy_done_confirmed_predecessor_unblocks(chained, service):
    db, store = service.db_for("draft"), DesktopV3State(service)
    current = store.read(**SCOPE)
    state = json.loads(json.dumps(current["state"]))
    state["nodes"].setdefault("b", {})["done"] = {"confirmed": True, "at": "2026-01-01T00:00:00Z", "by": "human",
                                                  "note": ""}
    with db:
        db.execute("UPDATE desktop_v3_state SET state=?, revision=revision+1 WHERE project_id='draft' AND"
                   " workspace_id='draft'", (json.dumps(state),))
    assert card(AgentState(service).read(**SCOPE), "a")["blockedBy"] == []
