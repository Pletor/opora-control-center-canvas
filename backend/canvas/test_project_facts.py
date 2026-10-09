import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.project_facts import validate_fact_refs
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed, send
from backend.canvas.test_canvas_plan_catalog import component


def save_fact(client, value):
    stored = client.get("/api/desktop-v3/state", params=SCOPE).json()
    stored["state"]["settings"] = [] if value is None else [{"id": "pilot", "key": "Pilot web", "value": value}]
    response = client.post("/api/desktop-v3/state", headers=HEADERS, json={**SCOPE, "state": stored["state"], "expectedRevision": stored["revision"]})
    assert response.status_code == 200, response.text


def test_fact_references_resolve_change_version_and_survive_restart(tmp_path):
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        digest = seed(client)
        save_fact(client, "https://old.example")
        plan = component()
        plan["nodes"][0]["factRefs"] = ["pilot"]
        response = send(client, digest, plan)
        assert response.status_code == 200, response.text
        params = {**SCOPE, "nodeId": response.json()["refs"]["component"]}
        before = client.get("/api/desktop-v3/node-brief", params=params).json()
        assert before["context"]["usedFacts"][0]["value"] == "https://old.example"
        save_fact(client, "https://new.example")
        after = client.get("/api/desktop-v3/node-brief", params=params).json()
        assert after["context"]["usedFacts"][0]["value"] == "https://new.example"
        assert after["contextVersion"] != before["contextVersion"]
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as client:
        assert client.get("/api/desktop-v3/node-brief", params=params).json()["node"]["factRefs"] == ["pilot"]
        save_fact(client, None)
        missing = client.get("/api/desktop-v3/node-brief", params=params).json()["context"]["usedFacts"][0]
        assert missing == {"id": "pilot", "key": "", "value": "", "missing": True}


@pytest.mark.parametrize("refs", ["pilot", ["pilot", "pilot"], ["bad id"], [None]])
def test_invalid_references(refs):
    with pytest.raises(ValueError):
        validate_fact_refs({"kind": "node", "factRefs": refs})
