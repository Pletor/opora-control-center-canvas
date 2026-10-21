"""The real HTTP boundary bounds imports and serves artifacts as inert attachments."""
import copy
import json

import pytest

from backend.api.editor.test_opora_changeset_routes import AGENT
from backend.api.editor.test_opora_execution_routes import BASE as EXECUTIONS
from backend.api.editor.test_opora_execution_routes import client as client  # noqa: PLC0414
from backend.api.editor.test_opora_execution_routes import payload
from backend.canvas.test_canvas_plan import ORIGIN, SCOPE
from backend.canvas.test_opora_verifications import artifact, verification

BASE = "/api/oporahub/verifications"


def imported(client):
    execution = client.post(EXECUTIONS + "/claim", headers=AGENT, json=payload(client)).json()
    body = {**SCOPE, "executionId": execution["executionId"], "token": execution["token"], "epoch": execution["epoch"],
            "requestId": "verification", "verification": verification()}
    return execution, body


def test_identity_scope_replay_and_inert_download(client):
    execution, body = imported(client)
    client.cookies.clear()
    assert client.post(BASE + "/requests", headers={"Origin": ORIGIN}, json=body).status_code == 428
    response = client.post(BASE + "/requests", headers=AGENT, json=body)
    assert response.status_code == 200, response.text
    saved = response.json()
    assert client.post(BASE + "/requests", headers=AGENT, json=body).json() == saved
    assert execution["token"] not in response.text and "dataBase64" not in response.text
    identifier = saved["id"]
    detail = client.get(BASE + "/" + identifier, params=SCOPE, headers=AGENT)
    assert detail.status_code == 200 and detail.json()["verification"]["artifacts"][0]["available"]
    assert client.get(BASE, params=SCOPE, headers=AGENT).json()["requests"][0]["id"] == identifier
    assert client.get(BASE + "/" + identifier, params={**SCOPE, "workspace": "other"}, headers=AGENT).status_code == 409
    fingerprint = saved["verification"]["artifacts"][0]["sha256"]
    download = client.get(BASE + "/" + identifier + "/artifacts/" + fingerprint, params=SCOPE, headers=AGENT)
    assert download.status_code == 200 and download.content.startswith(b"theorem")
    assert download.headers["content-type"] == "application/octet-stream"
    assert download.headers["content-disposition"].startswith("attachment;")
    assert download.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in download.headers["content-security-policy"]


@pytest.mark.parametrize("field", ["trust", "independentlyVerified", "acceptedRevision", "assignmentDigest"])
def test_caller_cannot_choose_authoritative_fields(client, field):
    _, body = imported(client)
    body[field] = "forged"
    assert client.post(BASE + "/requests", headers=AGENT, json=body).status_code == 409


def test_strict_json_and_stream_limit(client, monkeypatch):
    from backend.api.editor import opora_verification_routes as routes
    _, body = imported(client)
    headers = {**AGENT, "Content-Type": "application/json"}
    duplicate = json.dumps(body)[:-1] + ',"epoch":1}'
    assert client.post(BASE + "/requests", headers=headers, content=duplicate).status_code == 409
    for malformed in ('{"x":NaN}', '{"x":Infinity}', '{"x":', '[' * 1100):
        assert client.post(BASE + "/requests", headers=headers, content=malformed).status_code == 409
    monkeypatch.setattr(routes, "BODY_LIMIT", 30)
    response = client.post(BASE + "/requests", headers=headers, content=iter([b"x" * 20, b"y" * 20]))
    assert response.status_code == 413


def test_large_bounded_artifact_passes_former_two_mb_body_limit(client):
    _, body = imported(client)
    body["verification"]["artifacts"] = [artifact(data=b"x" * 1_600_000)]
    response = client.post(BASE + "/requests", headers=AGENT, json=body)
    assert response.status_code == 200, response.text
    assert response.json()["verification"]["artifacts"][0]["bytes"] == 1_600_000
    bad = copy.deepcopy(body)
    bad["requestId"] = "bad"
    bad["verification"]["tool"]["name"] = {}
    assert client.post(BASE + "/requests", headers=AGENT, json=bad).status_code == 409
