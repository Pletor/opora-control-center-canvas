"""Legacy mutation entry points cannot bypass durable execution enrollment."""
import copy

import pytest

from backend.api.editor.test_opora_execution_routes import AGENT, BASE, SCOPE, client, payload  # noqa: F401
from backend.canvas.test_canvas_plan import HEADERS


def enroll(client):
    response = client.post(BASE + "/claim", headers=AGENT, json=payload(client))
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("operation", ["remove", "node", "block", "legacy-claim", "legacy-heartbeat"])
def test_legacy_writes_refused_after_release(client, operation):
    record = enroll(client)
    client.post(BASE + "/" + record["executionId"] + "/release", headers=AGENT,
                json={**SCOPE, "token": record["token"], "epoch": record["epoch"]})
    before = client.get("/api/desktop-v3/state", params=SCOPE).json()
    node = copy.deepcopy(before["state"]["nodes"]["n0"])
    if operation == "remove":
        state = copy.deepcopy(before["state"])
        del state["nodes"]["n0"]
        path, body = "/state", {**SCOPE, "expectedRevision": before["revision"], "state": state}
    elif operation == "node":
        node["phase"] = "verify"
        path, body = "/node", {**SCOPE, "nodeId": "n0", "node": node, "expectedRevision": before["revision"]}
    elif operation == "block":
        path, body = "/block", {**SCOPE, "nodeId": "n0", "expectedRevision": before["revision"],
                                "op": {"kind": "update", "blockId": "b0", "patch": {"title": "Changed"}}}
    else:
        body = {**SCOPE, "nodeId": "n0", "op": operation.removeprefix("legacy-"), "ttlSeconds": 60}
        body.update({"owner": "legacy"} if operation == "legacy-claim" else {"token": record["token"]})
        path = "/lease"
    response = client.post("/api/desktop-v3" + path, headers=AGENT, json=body)
    assert response.status_code == 409, response.text
    assert client.get("/api/desktop-v3/state", params=SCOPE).json() == before


def test_human_edit_allowed_but_invalidates_execution(client):
    record = enroll(client)
    before = client.get("/api/desktop-v3/state", params=SCOPE).json()
    node = copy.deepcopy(before["state"]["nodes"]["n0"])
    node["blocks"][0]["title"] = "Human changed task"
    response = client.post("/api/desktop-v3/node", headers=HEADERS,
                           json={**SCOPE, "nodeId": "n0", "node": node, "expectedRevision": before["revision"]})
    assert response.status_code == 200, response.text
    heartbeat = client.post(BASE + "/" + record["executionId"] + "/heartbeat", headers=AGENT,
                            json={**SCOPE, "token": record["token"], "epoch": record["epoch"], "ttlSeconds": 60})
    assert heartbeat.status_code == 409


def test_agent_cannot_restore_version_or_realize_enrolled_card(client):
    enroll(client)
    assert client.post("/api/canvas-versions/restore", headers=AGENT, json={}).status_code == 403
    digest = client.get("/api/view", params=SCOPE).json()["digest"]
    response = client.post("/api/desktop-v3/realize-source", headers=AGENT,
                           json={**SCOPE, "nodeId": "n0", "digest": digest, "commit": "a" * 40, "prUrl": ""})
    assert response.status_code == 409 and "execution" in response.text.lower()


def test_legacy_agent_output_rejected_with_current_context_and_correct_token(client):
    record = enroll(client)
    before = client.get("/api/desktop-v3/state", params=SCOPE).json()
    brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "n0"}).json()
    response = client.post("/api/desktop-v3/agent-output", headers={**AGENT, "X-Opora-Lease": record["token"]},
                           json={**SCOPE, "nodeId": "n0", "expectedRevision": before["revision"],
                                 "contextVersion": brief["outputContract"]["request"]["contextVersion"], "agent": "builder",
                                 "output": {"schema": "opora.agent-output/1", "blocks": [], "reports": [],
                                            "done": {"proposed": True, "note": "Done"}, "decisions": []}})
    assert response.status_code == 409 and "receipts" in response.text, response.text
    assert client.get("/api/desktop-v3/state", params=SCOPE).json() == before


def test_pipeline_routing_refused_for_agent_but_available_to_human(client):
    enroll(client)
    before = client.get("/api/desktop-v3/state", params=SCOPE).json()
    body = {**SCOPE, "nodeId": "n0", "expectedRevision": before["revision"],
            "op": "route", "profile": "code", "reason": "Implementation"}
    response = client.post("/api/desktop-v3/pipeline", headers={**AGENT, "X-Opora-Actor": "agent; name=router-test"}, json=body)
    assert response.status_code == 409 and "receipts" in response.text, response.text
    response = client.post("/api/desktop-v3/pipeline", headers=HEADERS, json=body)
    assert response.status_code == 200, response.text


def test_noop_legacy_output_cannot_append_result_or_increment_revision(client):
    record = enroll(client)
    before = client.get("/api/desktop-v3/state", params=SCOPE).json()
    brief = client.get("/api/desktop-v3/node-brief", params={**SCOPE, "nodeId": "n0"}).json()
    response = client.post("/api/desktop-v3/agent-output", headers={**AGENT, "X-Opora-Lease": record["token"]},
                           json={**SCOPE, "nodeId": "n0", "expectedRevision": before["revision"],
                                 "contextVersion": brief["outputContract"]["request"]["contextVersion"], "agent": "builder",
                                 "output": {"schema": "opora.agent-output/1", "blocks": [], "reports": [],
                                            "done": {"proposed": False, "note": ""}, "decisions": []}})
    assert response.status_code == 409 and "execution" in response.text.lower(), response.text
    assert client.get("/api/desktop-v3/state", params=SCOPE).json() == before
    history = client.get("/api/desktop-v3/agent-results", params={**SCOPE, "nodeId": "n0"}).json()
    assert history["items"] == []
