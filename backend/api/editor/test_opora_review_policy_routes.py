"""Actual middleware prevents agent and unidentified policy activation."""
import pytest
from fastapi.testclient import TestClient

from backend.api.editor.test_opora_review_routes import HEADERS, ORIGIN
from backend.app.factory import create_app
from backend.canvas.test_opora_review_policy import evidence_fixture, policy_project

__all__ = ["evidence_fixture", "policy_project"]
BASE = "/api/oporahub/review-policy"


@pytest.fixture
def policy_client(policy_project):
    service, scope, payload = policy_project
    app = create_app(service.root)
    with TestClient(app, base_url=ORIGIN) as client:
        yield client, scope, payload


def test_human_policy_history_disable_and_agent_denial(policy_client):
    client, scope, payload = policy_client
    assert client.get(BASE, params=scope).json()["canConfigure"]
    agent = {**HEADERS, "X-Opora-Actor": "agent; name=worker"}
    assert client.get(BASE, params=scope, headers=agent).json()["canConfigure"] is False
    assert client.post(BASE, json=payload, headers=agent).status_code == 403
    created = client.post(BASE, json=payload, headers=HEADERS)
    assert created.status_code == 200, created.text
    head = created.json()["policyHead"]
    assert created.json()["policy"]["by"]["kind"] == "human"
    history = client.get(BASE + "/history", params=scope)
    assert history.status_code == 200 and len(history.json()["items"]) == 1
    assert client.post(BASE + "/disable", json={**scope, "expectedPolicyHead": head}, headers=agent).status_code == 403
    disabled = client.post(BASE + "/disable", json={**scope, "expectedPolicyHead": head}, headers=HEADERS)
    assert disabled.status_code == 200 and not disabled.json()["policy"]["enabled"]


def test_unknown_session_forged_body_and_cas_errors(policy_client):
    client, _, payload = policy_client
    assert client.post(BASE, json={**payload, "by": {"kind": "human"}}, headers=HEADERS).status_code == 409
    created = client.post(BASE, json=payload, headers=HEADERS)
    assert created.status_code == 200, created.text
    changed = {**payload, "rules": {**payload["rules"], "maxObservationAgeSeconds": 60}}
    assert client.post(BASE, json=changed, headers=HEADERS).status_code == 409
    client.cookies.clear()
    assert client.post(BASE, json=payload, headers=HEADERS).status_code == 428
