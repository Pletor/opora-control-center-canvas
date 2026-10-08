import copy

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.graph import validate_graph
from backend.canvas.test_canvas_plan import GRAPH, HEADERS, ORIGIN, SCOPE, seed, send
from backend.editor.agent_memory.autonomy import authorize_close
from backend.editor.agent_memory.test_completion_evidence import evidence
from backend.editor.agent_packet.sector_status import sector_status


def test_explicit_gate_is_scoped_and_requires_human_closure():
    graph = copy.deepcopy(GRAPH)
    graph["nodes"][0]["gateNodeId"] = "n0"
    validate_graph(graph)
    state = {"nodes": {"n0": {"done": {"confirmed": True, "by": "autonomy"}}}}
    assert sector_status(graph, state)["s0"]["status"] == "running"
    state["nodes"]["n0"]["done"]["by"] = "human"
    assert sector_status(graph, state)["s0"] == {"gateNodeId": "n0", "status": "verified", "closed": 1, "total": 1}
    graph["nodes"].append({**graph["nodes"][1], "id": "unfinished"})
    assert sector_status(graph, state)["s0"]["status"] == "running"
    graph["nodes"][0]["gateNodeId"] = "missing"
    with pytest.raises(ValueError):
        validate_graph(graph)


def test_plan_resolves_gate_reference_and_brief_reports_progress(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        digest = seed(client)
        plan = {"nodes": [{"ref": "sector", "kind": "sector", "name": "New", "gateNodeId": "gate"},
                          {"ref": "gate", "kind": "node", "name": "Acceptance", "parent": "sector"}]}
        result = send(client, digest, plan)
        assert result.status_code == 200, result.text
        refs = result.json()["refs"]
        graph = client.get("/api/view", params=SCOPE).json()["graph"]
        assert next(n for n in graph["nodes"] if n["id"] == refs["sector"])["gateNodeId"] == refs["gate"]
        brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": refs["gate"]}).json()
        assert brief["context"]["sectorVerification"][refs["sector"]]["status"] == "running"
        state = {"autonomy": {refs["sector"]: {"until": "2099-01-01T00:00:00Z"}}, "nodes": {}}
        with pytest.raises(ValueError, match="člověk"):
            authorize_close(graph, state, refs["gate"], "2026-10-07T00:00:00Z")


def test_unverified_sector_blocks_frontier_claim_and_output_until_human_gate(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        view = client.get("/api/view", params=SCOPE).json()
        graph = view["graph"]
        graph["nodes"][0]["gateNodeId"] = "n0"
        graph["nodes"].extend([
            {"id": "s1", "kind": "sector", "parentId": None, "name": "Next", "purpose": "", "x": 0, "y": 0},
            {"id": "n1", "kind": "node", "parentId": "s1", "name": "Work", "purpose": "", "x": 0, "y": 0},
        ])
        graph["edges"].append({"id": "next", "source": "s0", "target": "s1"})
        assert client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": graph, "digest": view["digest"]}).status_code == 200
        lease = {**SCOPE, "nodeId": "n1", "op": "claim", "owner": "agent", "ttlSeconds": 60}
        assert client.post("/api/desktop-v3/lease", headers=HEADERS, json=lease).status_code == 409
        def output():
            brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "n1"}).json()
            return client.post("/api/desktop-v3/agent-output", headers=HEADERS, json={
                **brief["outputContract"]["request"], "agent": "worker", "output": {
                    "schema": "opora.agent-output/1", "blocks": [], "reports": [], "decisions": [], "done": {"proposed": False, "note": ""}}})
        assert output().status_code == 409
        result = client.get("/api/desktop-v3/frontier", params={**SCOPE, "nodeId": "s1"}).json()
        assert result["blocked"][0]["blockedBy"][0]["id"] == "s0"
        stored = client.get("/api/desktop-v3/state", params=SCOPE).json()
        stored["state"]["nodes"]["n0"]["done"] = {"confirmed": True, "by": "human", "at": "2026-10-07T12:00:00Z", "note": "Verified"}
        stored["state"]["nodes"]["n0"]["evidence"] = evidence()
        assert client.post("/api/desktop-v3/state", headers=HEADERS, json={**SCOPE, "state": stored["state"], "expectedRevision": stored["revision"]}).status_code == 200
        assert client.post("/api/desktop-v3/lease", headers=HEADERS, json=lease).status_code == 200
        assert output().status_code == 200


def _two_sectors(edge_source):
    from backend.editor.agent_packet.sector_status import sector_blockers
    graph = copy.deepcopy(GRAPH)
    graph["nodes"].extend([
        {"id": "s1", "kind": "sector", "parentId": None, "name": "Next", "purpose": "", "x": 0, "y": 0},
        {"id": "n1", "kind": "node", "parentId": "s1", "name": "Work", "purpose": "", "x": 0, "y": 0},
    ])
    graph["edges"].append({"id": "next", "source": edge_source, "target": "s1"})
    return graph, sector_blockers


def test_sector_without_gate_is_fail_closed_until_its_cards_are_closed():
    """Kritika #33: smazané `gateNodeId` zámek neruší, sektor bez brány čeká na uzavření karet."""
    graph, sector_blockers = _two_sectors("s0")
    open_state = {"nodes": {}}
    assert [b["id"] for b in sector_blockers(graph, open_state, "n1")] == ["s0"]
    closed = {"nodes": {"n0": {"done": {"confirmed": True, "by": "human"}}}}
    assert sector_blockers(graph, closed, "n1") == []


def test_skill_recipe_card_to_next_sector_also_locks_it():
    """Kritika #33: recept „Ověření sektoru“ (karta → next → sektor) musí zamknout karty dalšího sektoru."""
    graph, sector_blockers = _two_sectors("n0")
    assert [b["id"] for b in sector_blockers(graph, {"nodes": {}}, "n1")] == ["n0"]
    assert sector_blockers(graph, {"nodes": {"n0": {"done": {"confirmed": True, "by": "human"}}}}, "n1") == []
