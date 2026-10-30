from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import ORIGIN, SCOPE, seed
from backend.editor.agent_packet.frontier import frontier


def test_frontier_api_reads_sector_and_root(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        result = client.get("/api/desktop-v3/frontier", params={**SCOPE, "nodeId": "s0"})
        assert result.status_code == 200, result.text
        assert [r["id"] for r in result.json()["frontier"]] == ["n0"]
        assert client.get("/api/desktop-v3/frontier", params=SCOPE).status_code == 200
        assert client.get("/api/desktop-v3/frontier", params={**SCOPE, "nodeId": "missing"}).status_code == 409


def test_frontier_prioritizes_waiting_claims_dependencies_and_closure():
    graph = {"nodes": [{"id": "s", "kind": "sector"}] + [{"id": n, "kind": "node", "parentId": "s", "name": n} for n in ("a", "b", "c")],
             "edges": [{"id": "e", "source": "a", "target": "b"}]}
    state = {"nodes": {"c": {"blocks": [{"id": "block", "state": {"status": "blocked", "note": "Need URL"}}]}}}
    result = frontier(graph, state, "s", {"a": "Převzato: agent"})
    assert result["claimed"][0]["claim"] == "agent"
    assert result["blocked"][0]["blockedBy"] == [{"id": "a", "name": "a"}]
    assert result["waiting"][0]["waitingOnHuman"][0]["ask"] == "Need URL"
    state["nodes"]["a"] = {"done": {"confirmed": True}}
    result = frontier(graph, state, "s", {})
    assert [r["id"] for r in result["frontier"]] == ["b"]
    assert [r["id"] for r in result["closed"]] == ["a"]


def test_merged_and_written_back_card_frees_its_successor_and_waits_for_closure():
    """Jako agent-state: sloučené PR zapsané do plánu už neblokuje následníka; samo čeká na uzavření člověkem."""
    graph = {"nodes": [{"id": "s", "kind": "sector"}] + [{"id": n, "kind": "node", "parentId": "s", "name": n} for n in ("a", "b")],
             "edges": [{"id": "e", "source": "a", "target": "b"}]}
    result = frontier(graph, {"nodes": {}}, "s", {}, merged={"a"})
    assert [r["id"] for r in result["frontier"]] == ["b"]
    assert [r["id"] for r in result["waiting"]] == ["a"] and "uzavře člověk" in result["waiting"][0]["waitingOnHuman"][0]["ask"]
