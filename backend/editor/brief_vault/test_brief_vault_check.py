"""Poradní kontrola brány přes Jev (docs/schranka-neurony.md §7, §9 bod 10): povolení, revize, co odchází, klíč."""
import io
import json
import logging

import pytest

from backend.app.remote_access import is_loopback_only
from backend.editor.brief_vault.brief_vault_check import MAX_TEXT, gate_check
from backend.editor.brief_vault.test_brief_vault_discipline import AGENT, SCOPE, post
from backend.editor.brief_vault.test_brief_vault_gates import WEIGHED, vault_client
from backend.editor.node.test_removals import HEADERS
from backend.integrations import typesafe_client
from backend.integrations.typesafe_client import CELERIS_ENDPOINT, CELERIS_MODEL

SECRET = "cel-secret-123"


class FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeOpener:
    """Místo sítě: zaznamená požadavek a vrátí odpověď Jev."""

    def __init__(self, calls, noul=0.8):
        self.calls, self.noul = calls, noul

    def open(self, request, timeout):
        self.calls.append({"url": request.full_url, "headers": dict(request.header_items()),
                           "body": json.loads(request.data)})
        return FakeResponse(json.dumps({"answers": {"satisfied": {"type": "noul", "noul": self.noul}}}).encode())


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("OPORA_JEV_PROVIDER", "celeris")
    monkeypatch.delenv("CELERIS_API_KEY", raising=False)
    calls = []
    monkeypatch.setattr(typesafe_client, "build_opener", lambda: FakeOpener(calls))
    with vault_client(tmp_path) as client:
        fragment = post(client, op="create", scopeNodeId="s1", discipline="db", title="Import",
                        text="x" * (MAX_TEXT + 500))["fragment"]
        yield client, fragment, calls


def check(client, fragment, expect=200, **extra):
    body = {**SCOPE, "fragmentId": fragment["id"], "expectedRevision": fragment["revision"], "gate": "weighed",
            "payload": WEIGHED, **extra}
    response = client.post("/api/brief-vault/gate-check", headers=AGENT, json=body)
    assert response.status_code == expect, response.text
    return response


def allow(client, value=True):
    response = client.post("/api/brain/jev/gate-check",
                           headers=HEADERS, json={"project": SCOPE["project"], "provider": "celeris", "allowed": value})
    assert response.status_code == 200, response.text


def test_without_permission_no_network_even_with_key(setup):
    client, fragment, calls = setup
    assert client.post("/api/brain/jev/key", headers=HEADERS, json={"key": SECRET, "provider": "celeris"}).status_code == 200
    result = check(client, fragment).json()
    assert result["probability"] is None and result["reason"] == "not-allowed" and result["provider"] == "celeris"
    assert len(result["inputHash"]) == 64
    assert calls == []


def test_permission_without_key_is_not_configured(setup):
    client, fragment, calls = setup
    allow(client)
    assert check(client, fragment).json()["reason"] == "not-configured"
    assert calls == []


def test_allowed_sends_only_title_text_gate_payload(setup, caplog):
    client, fragment, calls = setup
    client.post("/api/brain/jev/key", headers=HEADERS, json={"key": SECRET, "provider": "celeris"})
    allow(client)
    with caplog.at_level(logging.DEBUG):
        response = check(client, fragment)
    result = response.json()
    assert result["probability"] == 0.8 and result["provider"] == "celeris" and "reason" not in result
    assert SECRET not in response.text and SECRET not in caplog.text
    [call] = calls
    assert call["url"] == CELERIS_ENDPOINT and call["headers"]["Authorization"] == f"Bearer {SECRET}"
    body = call["body"]
    assert set(body) == {"state", "model", "questions"} and body["model"] == CELERIS_MODEL
    assert body["state"] == {"title": "Import", "text": "x" * MAX_TEXT, "gate": "weighed", "payload": WEIGHED}
    assert SECRET not in json.dumps(body)
    [(_name, asked)] = body["questions"].items()
    assert asked["type"] == "noul" and "weighed" in asked["instructions"]
    assert "Import" not in asked["instructions"] and "Rychlejší" not in asked["instructions"]
    # zakázání platí hned
    allow(client, False)
    assert check(client, fragment).json()["reason"] == "not-allowed" and len(calls) == 1


def test_stale_revision_is_409_and_bad_shape_400(setup):
    client, fragment, calls = setup
    allow(client)
    check(client, fragment, expect=409, expectedRevision=fragment["revision"] + 1)
    check(client, fragment, expect=400, gate="neni")
    check(client, fragment, expect=400, payload={"benefit": "jen přínos"})
    check(client, fragment, expect=409, fragmentId="neexistuje")
    assert calls == []


def test_permission_is_per_provider(setup):
    client, fragment, _calls = setup
    settings_calls = []

    class Settings:
        def gate_check_allowed(self, project, provider):
            settings_calls.append(provider)
            return provider == "typesafe"

        def jev_key(self, provider):
            return "k"

    service = client.app_state.service
    body = {**SCOPE, "fragmentId": fragment["id"], "expectedRevision": fragment["revision"], "gate": "weighed",
            "payload": WEIGHED}
    sent = []
    result = gate_check(service, body, settings=Settings(), provider="celeris",
                        evaluate=lambda *a, **k: sent.append(k) or {})
    assert result["reason"] == "not-allowed" and sent == [] and settings_calls == ["celeris"]
    result = gate_check(service, body, settings=Settings(), provider="typesafe",
                        evaluate=lambda *a, **k: sent.append(k) or {"satisfied": {"noul": 2}})
    assert result["reason"] == "unavailable" and sent == [{"key": "k", "provider": "typesafe"}]


def test_agent_cannot_grant_permission(setup):
    client, _fragment, _calls = setup
    refused = client.post("/api/brain/jev/gate-check", headers=AGENT,
                          json={"project": SCOPE["project"], "provider": "celeris", "allowed": True})
    assert refused.status_code == 403
    assert client.get("/api/brain/jev/gate-check", params={"project": SCOPE["project"]}).json()["allowed"] == {
        "typesafe": False, "celeris": False}


def test_gate_check_is_loopback_only():
    assert is_loopback_only("/api/brief-vault/gate-check")
