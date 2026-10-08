from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.editor.agent_memory.test_agent_output import HEADERS, ORIGIN, SCOPE, prepared, send
from backend.editor.agent_memory.test_versioned_output import brief, result_request
from backend.editor.agent_memory.test_completion_evidence import evidence


def test_human_confirms_agent_proposal_with_cas_and_persistence(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        prepared(client)
        assert send(client, result_request(brief(client))).status_code == 200
        saved = client.get("/api/desktop-v3/state", params=SCOPE).json()
        done = saved["state"]["nodes"]["focus"]["done"]
        assert done["by"] == "agent" and not done["confirmed"]
        done.update(confirmed=True, by="human")
        payload = {**SCOPE, "state": saved["state"], "expectedRevision": saved["revision"]}
        assert client.post("/api/desktop-v3/state", headers=HEADERS, json=payload).status_code == 409
        payload["state"]["nodes"]["focus"]["evidence"] = evidence()
        assert client.post("/api/desktop-v3/state", headers=HEADERS, json=payload).status_code == 200
        assert client.post("/api/desktop-v3/state", headers=HEADERS, json=payload).status_code == 409
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        done = client.get("/api/desktop-v3/state", params=SCOPE).json()["state"]["nodes"]["focus"]["done"]
        assert done["confirmed"] and done["by"] == "human"
