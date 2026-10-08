from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.agent_memory.test_agent_output import HEADERS, ORIGIN, SCOPE, prepared, send
from backend.editor.agent_memory.test_versioned_output import brief, result_request


def test_downstream_brief_has_source_decision_port_and_handoff(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        prepared(client)
        request = result_request(brief(client))
        request["output"]["ports"] = [{"blockId": "b1", "portId": "p1", "status": "chosen", "reason": "Meets latency"}]
        assert send(client, request).status_code == 200
        response = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "dalsi"})
        assert response.status_code == 200, response.text
        upstream = response.json()["context"]["upstreamDecisions"]
        assert len(upstream) == 1
        item = upstream[0]
        assert item["nodeId"] == "focus" and item["edgeId"] == "e-out"
        assert item["sourcePort"]["status"] == "chosen"
        assert item["chosenPorts"][0]["reason"] == "Meets latency"
        assert item["decisions"][0]["text"] == request["output"]["decisions"][0]
        assert item["report"]["handoff"] == request["output"]["reports"][0]["handoff"]
        assert brief(client)["context"]["upstreamDecisions"] == []
        # A rejected link remains explicit rather than looking like a chosen dependency.
        stored = client.get("/api/desktop-v3/state", params=SCOPE).json()
        stored["state"]["nodes"]["focus"]["blocks"][0]["ports"][0]["status"] = "rejected"
        saved = client.post("/api/desktop-v3/state", headers=HEADERS, json={**SCOPE, "state": stored["state"], "expectedRevision": stored["revision"]})
        assert saved.status_code == 200, saved.text
        item = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "dalsi"}).json()["context"]["upstreamDecisions"][0]
        assert item["sourcePort"]["status"] == "rejected" and item["chosenPorts"] == []
