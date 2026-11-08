"""Readback verifies content, not merely identity or an advanced revision."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from backend.canvas.operation_readback import verify_plan
from backend.canvas.payload_errors import NextStep
from backend.editor.agent_memory.desktop_v3_state import fill_defaults


def fixture():
    graph = {"nodes": [{"id": "a", "name": "Expected", "x": 1.6, "y": 2.1},
                       {"id": "b", "name": "Target", "x": 10, "y": 20}],
             "edges": [{"id": "e", "source": "a", "target": "b", "port": "next", "carries": "data"}]}
    state = {"nodes": {"a": {"phase": "discover", "criteria": [], "steps": []}}}
    built = SimpleNamespace(new_graph=lambda: graph, state=state, specs={"a": {"goal": "Full goal"}},
                            texts={"a": "Full text"})
    saved = deepcopy(graph)
    saved["nodes"][0].update(x=2, y=2)
    stored = {"revision": 7, "state": fill_defaults(deepcopy(state))}
    reads = []
    def read_spec(key):
        reads.append(key)
        return {"fields": {"goal": "Full goal"}}
    service = SimpleNamespace(specs=SimpleNamespace(read=read_spec),
                              texts=SimpleNamespace(read=lambda key: {"text": "Full text"}))
    store = SimpleNamespace(current=lambda *args: stored)
    return built, saved, stored, service, store, reads


@pytest.mark.parametrize("corrupt", ["name", "edge", "state", "revision", "duplicate"])
def test_same_ids_do_not_prove_saved_content(corrupt):
    built, saved, stored, service, store, _ = fixture()
    if corrupt == "name":
        saved["nodes"][0]["name"] = "Wrong"
    elif corrupt == "edge":
        saved["edges"][0].update(source="b", target="a")
    elif corrupt == "state":
        stored["state"]["nodes"]["a"]["phase"] = "live"
    elif corrupt == "revision":
        stored["revision"] += 1
    else:
        saved["nodes"].append(deepcopy(saved["nodes"][0]))
    with pytest.raises(NextStep) as error:
        verify_plan(service, store, "p", "w", built, lambda node: "architecture", {"graph": saved}, 7)
    assert error.value.code == "operation_incomplete"


def test_native_coordinate_rounding_defaults_and_document_workspace():
    built, saved, _, service, store, reads = fixture()
    saved["nodes"].reverse()
    verify_plan(service, store, "p", "w", built, lambda node: "architecture", {"graph": saved}, 7)
    assert reads == [("p", "architecture", "a")]
    assert "settings" not in built.state  # default filling does not mutate the prepared write
