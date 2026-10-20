"""Session attribution and additive API workflow for specifications-only proposals."""
import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, seed

AGENT = {**HEADERS, "X-Opora-Actor": "agent; name=builder"}
BASE = "/api/oporahub"


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as instance:
        seed(instance)
        yield instance


def context(client):
    response = client.get(BASE + "/changesets/context", params=SCOPE)
    assert response.status_code == 200, response.text
    return response.json()


def baseline_payload(client):
    value = context(client)
    return {**SCOPE, "subject": "Initial specs", "expectedAcceptedHead": None,
            "expectedGraphDigest": value["graphDigest"], "expectedSpecificationsVersion": value["specificationsVersion"]}


def proposal_payload(client):
    value = context(client)
    doc = next(item for item in value["documents"] if item["nodeId"] == "n0")
    return {**SCOPE, "subject": "Reviewed change", "parentRevision": value["acceptedHead"],
            "expectedGraphDigest": value["graphDigest"], "by": {"kind": "human", "name": "forged"},
            "changes": [{"nodeId": "n0", "expectedRevision": doc["revision"],
                         "fields": {**doc["fields"], "goal": "New requested goal"}}]}


def test_api_baseline_propose_read_accept_and_identity(client):
    payload = baseline_payload(client)
    assert client.post(BASE + "/baselines", headers=AGENT, json=payload).status_code == 403
    baseline = client.post(BASE + "/baselines", headers=HEADERS, json=payload)
    assert baseline.status_code == 200, baseline.text
    created = client.post(BASE + "/changesets", headers=AGENT, json=proposal_payload(client))
    assert created.status_code == 200, created.text
    proposal = created.json()
    assert proposal["by"] == {"kind": "agent", "name": "builder"}
    assert client.get(BASE + "/changesets/" + proposal["id"], params=SCOPE).json() == proposal
    assert client.get(BASE + "/changesets", params=SCOPE).json()["items"] == [proposal]
    assert next(item for item in context(client)["documents"] if item["nodeId"] == "n0")["fields"]["goal"] == ""
    endpoint = BASE + "/changesets/" + proposal["id"] + "/accept"
    acceptance = {**SCOPE, "expectedAcceptedHead": baseline.json()["id"], "by": {"kind": "human"}}
    assert client.post(endpoint, headers=AGENT, json=acceptance).status_code == 403
    accepted = client.post(endpoint, headers=HEADERS, json=acceptance)
    assert accepted.status_code == 200, accepted.text
    assert context(client)["acceptedHead"] == accepted.json()["id"]
    assert client.get(BASE + "/revisions/" + accepted.json()["id"], params=SCOPE).json() == accepted.json()
    assert client.get(BASE + "/revisions/" + baseline.json()["id"], params=SCOPE).json() == baseline.json()
    assert client.get(BASE + "/revisions/" + baseline.json()["id"],
                      params={**SCOPE, "workspace": "other"}).status_code == 409
    assert client.post(endpoint, headers=HEADERS, json=acceptance).status_code == 409
    assert client.get(BASE + "/changesets/" + proposal["id"], params=SCOPE).json()["accepted"]


def test_unknown_actor_cannot_initialize_propose_accept_or_rebase(client):
    initial = baseline_payload(client)
    client.post(BASE + "/baselines", headers=HEADERS, json=initial)
    proposal = proposal_payload(client)
    created = client.post(BASE + "/changesets", headers=AGENT, json=proposal).json()
    client.cookies.clear()
    for endpoint, payload in [
        ("/baselines", initial), ("/changesets", proposal),
        ("/changesets/" + created["id"] + "/accept", SCOPE),
        ("/changesets/" + created["id"] + "/rebase", SCOPE),
    ]:
        response = client.post(BASE + endpoint, headers=HEADERS, json=payload)
        assert response.status_code == 428, response.text


def test_stale_baseline_observation_and_cross_workspace_read_are_rejected(client):
    payload = baseline_payload(client)
    payload["expectedSpecificationsVersion"] = "0" * 64
    assert client.post(BASE + "/baselines", headers=HEADERS, json=payload).status_code == 409
    assert context(client)["acceptedHead"] is None
    assert client.post(BASE + "/baselines", headers=HEADERS, json=baseline_payload(client)).status_code == 200
    created = client.post(BASE + "/changesets", headers=AGENT, json=proposal_payload(client)).json()
    response = client.get(BASE + "/changesets/" + created["id"], params={**SCOPE, "workspace": "other"})
    assert response.status_code == 409
