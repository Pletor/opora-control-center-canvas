"""Evidence HTTP boundary rejects payload verdicts and derives initiator identity."""
import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_opora_review_fixtures import Reader
from backend.canvas.test_opora_review_fixtures import (
    evidence_project as evidence_fixture,  # noqa: F401
)
from backend.integrations.github_review_reader import GitHubReviewReader

ORIGIN = "http://127.0.0.1:8740"
HEADERS = {"origin": ORIGIN}


@pytest.fixture
def client(evidence_project, monkeypatch):
    service, payload = evidence_project
    reader = Reader(payload)
    monkeypatch.setattr(GitHubReviewReader, "read", lambda self, repository, number: reader.read(repository, number))
    app = create_app(service.root)
    with TestClient(app, base_url=ORIGIN) as client:
        yield client, payload, reader


def test_http_list_import_full_read_and_actor_attribution(client):
    client, payload, reader = client
    scope = {key: payload[key] for key in ("project", "workspace")}
    assert client.get("/api/oporahub/github-evidence", params=scope).json()["items"] == []
    response = client.post("/api/oporahub/github-evidence", json=payload,
                           headers={**HEADERS, "X-Opora-Actor": "agent; name=researcher"})
    assert response.status_code == 200, response.text
    record = response.json()["snapshot"]
    assert record["initiatedBy"] == {"kind": "agent", "name": "researcher"}
    assert reader.calls == [("owner/repo", 1)]
    history = client.get("/api/oporahub/github-evidence", params=scope).json()
    assert len(history["items"]) == 1
    summary = history["items"][0]["snapshot"]
    assert summary["id"] == record["id"] and summary["counts"]["reviews"] == 1
    assert "reviews" not in summary and "body" not in summary["pr"]
    read = client.get("/api/oporahub/github-evidence/" + record["id"], params=scope)
    assert read.json()["snapshot"] == response.json()["snapshot"]
    assert read.json()["evaluation"] == response.json()["evaluation"]
    assert read.json()["policyEvaluation"]["status"] == "not_configured"
    foreign = client.get("/api/oporahub/github-evidence/" + record["id"], params={**scope, "workspace": "main"})
    assert foreign.status_code == 409


def test_http_unknown_identity_forged_verdict_and_local_project(client):
    client, payload, reader = client
    assert client.post("/api/oporahub/github-evidence", json={**payload, "initiatedBy": {"kind": "human"}}, headers=HEADERS).status_code == 409
    assert client.post("/api/oporahub/github-evidence", json={**payload, "reviews": []}, headers=HEADERS).status_code == 409
    client.cookies.clear()
    assert client.post("/api/oporahub/github-evidence", json=payload, headers=HEADERS).status_code == 428
    assert not reader.calls
    local = client.get("/api/oporahub/github-evidence", params={"project": "draft", "workspace": "draft"})
    assert local.status_code == 200 and local.json()["available"] is False
