from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed
from backend.editor.agent_memory.test_completion_evidence import evidence
from backend.editor.agent_packet.sector_status import sector_status


def run_result(client, failed=0, command="uv run python -m e2e"):
    brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "n0"}).json()
    run = {"command": command, "at": "2026-10-07T12:00:00Z", "passed": 31 - failed, "failed": failed,
           "logUrl": "https://ci.example/e2e/log", "firstFailure": "Isolation" if failed else ""}
    return client.post("/api/desktop-v3/agent-output", headers=HEADERS, json={**brief["outputContract"]["request"], "agent": "worker",
        "output": {"schema": "opora.agent-output/1", "blocks": [], "reports": [], "decisions": [],
                   "done": {"proposed": False, "note": ""}, "scenarioRun": run}})


def test_scenario_results_and_comparison_survive_restart_and_command_change(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        view = client.get("/api/view", params=SCOPE).json()
        node = next(n for n in view["graph"]["nodes"] if n["id"] == "n0")
        node.update(name="[gate] Verification", scenario={"command": "uv run python -m e2e"})
        assert client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": view["graph"], "digest": view["digest"]}).status_code == 200
        brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "n0"}).json()
        assert brief["node"]["type"] == "gate"
        assert run_result(client, command="different").status_code == 409
        assert run_result(client, 1).status_code == 200
        assert run_result(client).status_code == 200
        history = client.get("/api/desktop-v3/scenario-history", params=SCOPE).json()["nodes"]["n0"]
        assert history["latest"]["passed"] == 31 and history["previous"]["firstFailure"] == "Isolation"
        assert history["comparable"] and history["deltaFailed"] == -1 and history["deltaPassed"] == 1
        assert client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "n0"}).json()["contextVersion"] == brief["contextVersion"]
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        assert client.get("/api/desktop-v3/scenario-history", params=SCOPE).json()["nodes"]["n0"]["latest"]["passed"] == 31
        view = client.get("/api/view", params=SCOPE).json()
        next(n for n in view["graph"]["nodes"] if n["id"] == "n0")["scenario"]["command"] = "new command"
        assert client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": view["graph"], "digest": view["digest"]}).status_code == 200
        history = client.get("/api/desktop-v3/scenario-history", params=SCOPE).json()["nodes"]["n0"]
        assert not history["current"] and not history["comparable"] and history["deltaFailed"] is None


def test_gate_cannot_close_with_failed_scenario(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        seed(client)
        view = client.get("/api/view", params=SCOPE).json()
        next(n for n in view["graph"]["nodes"] if n["id"] == "n0")["scenario"] = {"command": "uv run python -m e2e"}
        assert client.post("/api/graph", headers=HEADERS, json={**SCOPE, "graph": view["graph"], "digest": view["digest"]}).status_code == 200
        for failures, expected_status in ((1, 409), (0, 200)):
            assert run_result(client, failures).status_code == 200
            stored = client.get("/api/desktop-v3/state", params=SCOPE).json()
            stored["state"]["nodes"]["n0"].update(evidence=evidence(), done={"confirmed": True, "by": "human", "at": "2026-10-07T12:00:00Z", "note": "Verified"})
            result = client.post("/api/desktop-v3/state", headers=HEADERS, json={**SCOPE, "expectedRevision": stored["revision"], "state": stored["state"]})
            assert result.status_code == expected_status, result.text


def test_changed_gate_command_invalidates_sector_verification():
    graph = {"nodes": [{"id": "s", "parentId": None, "kind": "sector", "gateNodeId": "g"},
                       {"id": "g", "parentId": "s", "kind": "node", "scenario": {"command": "new"}}], "edges": []}
    state = {"nodes": {"g": {"done": {"confirmed": True, "by": "human"}, "scenarioRun": {"command": "old", "failed": 0}}}}
    assert sector_status(graph, state)["s"]["status"] == "running"
    state["nodes"]["g"]["scenarioRun"]["command"] = "new"
    assert sector_status(graph, state)["s"]["status"] == "verified"
