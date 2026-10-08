import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.agent_memory.test_agent_output import HEADERS, ORIGIN, SCOPE, prepared
from backend.editor.agent_memory.test_versioned_output import brief
from backend.editor.agent_memory.test_versioned_output import result_request
from backend.editor.agent_memory.test_agent_output import send


def test_port_decision_roundtrip_and_brief(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        prepared(client)
        before = brief(client)
        stored = client.get("/api/desktop-v3/state", params=SCOPE).json()
        port = stored["state"]["nodes"]["focus"]["blocks"][0]["ports"][0]
        port.update(status="chosen", reason="Meets the latency requirement")
        response = client.post("/api/desktop-v3/state", headers=HEADERS, json={**SCOPE, "state": stored["state"], "expectedRevision": stored["revision"]})
        assert response.status_code == 200, response.text
        after = brief(client)
        assert after["blocks"][0]["ports"][0]["reason"] == port["reason"]
        assert after["contextVersion"] != before["contextVersion"]
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        assert brief(client)["blocks"][0]["ports"][0]["status"] == "chosen"


@pytest.mark.parametrize("patch", [{"status": "chosen"}, {"reason": "alone"}, {"status": "wrong", "reason": "why"}, {"status": "rejected", "reason": " "}])
def test_invalid_port_decision_is_atomic(tmp_path, patch):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        prepared(client)
        stored = client.get("/api/desktop-v3/state", params=SCOPE).json()
        stored["state"]["nodes"]["focus"]["blocks"][0]["ports"][0].update(patch)
        response = client.post("/api/desktop-v3/state", headers=HEADERS, json={**SCOPE, "state": stored["state"], "expectedRevision": stored["revision"]})
        assert response.status_code == 409, response.text
        assert client.get("/api/desktop-v3/state", params=SCOPE).json()["revision"] == stored["revision"]


def test_agent_decides_existing_port_and_rejects_unknown_without_partial_output(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        prepared(client)
        assignment = brief(client)
        request = result_request(assignment)
        request["output"]["ports"] = [{"blockId": "b1", "portId": "missing", "status": "rejected", "reason": "Too slow"}]
        assert send(client, request).status_code == 409
        after = brief(client)
        assert after["resultHistory"]["items"] == []
        assert after["blocks"] == assignment["blocks"]
        request["output"]["ports"][0]["portId"] = "p1"
        response = send(client, request)
        assert response.status_code == 200, response.text
        port = brief(client)["blocks"][0]["ports"][0]
        assert port["status"] == "rejected" and port["reason"] == "Too slow"
        assert response.json()["acceptedResult"]["output"]["ports"] == request["output"]["ports"]
