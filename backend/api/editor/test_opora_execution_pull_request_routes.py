"""Actual factory/middleware: identity, lease credentials, link, 404 and conflict status codes."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.test_opora_execution_pull_requests import SHA, pr
from backend.canvas.test_opora_review_fixtures import setup
from backend.integrations.github_pr_link_reader import GitHubPullRequestLinkReader
from database.schema.opora_execution_pull_request_schema import TABLES
from database.schema.project_schema import PROJECT_TABLES

ORIGIN = "http://127.0.0.1:8740"
AGENT = {"origin": ORIGIN, "X-Opora-Actor": "agent; name=worker"}


def test_factory_link_read_and_conflicts(tmp_path, monkeypatch):
    monkeypatch.setenv("OPORA_RECONCILIATION_WORKER", "0")
    monkeypatch.setenv("OPORA_EXECUTION_PR_WORKER", "0")
    calls = []
    monkeypatch.setattr(GitHubPullRequestLinkReader, "pull_request",
                        lambda self, repository, number: calls.append(number) or pr(number))
    from backend.canvas.test_canvas_service import managed_fixture
    fixture, project = managed_fixture(tmp_path)
    fixture.close()
    app = create_app(tmp_path / "data")
    with TestClient(app, base_url=ORIGIN) as client:
        service = app.state.service
        assert set(TABLES) <= PROJECT_TABLES.keys()
        scope = setup(service, project["id"])
        scope = {"project": scope["project"], "workspace": scope["workspace"]}
        executions = ExecutionResults(service)
        context = executions.context(**scope, node="card")
        record = executions.claim({**scope, "nodeId": "card", "requestId": "claim", "ttlSeconds": 60,
                                   "expectedAcceptedHead": context["acceptedHead"],
                                   "expectedContextVersion": context["contextVersion"]}, "agent:worker")
        path = f"/api/oporahub/executions/{record['executionId']}/pull-request"
        body = {**scope, "token": record["token"], "epoch": record["epoch"], "requestId": "link",
                "repository": "owner/repo", "number": 7, "headRef": "feature", "headSha": SHA}
        client.cookies.clear()
        assert client.post(path, headers={"origin": ORIGIN}, json=body).status_code == 428
        assert client.get(path, headers=AGENT, params=scope).status_code == 404
        assert client.post(path, headers=AGENT, json={**body, "epoch": record["epoch"] + 1}).status_code == 409
        created = client.post(path, headers=AGENT, json=body)
        assert created.status_code == 200, created.text
        assert created.json()["state"] == "open" and created.json()["bindingId"] and calls == [7]
        assert client.get(path, headers=AGENT, params=scope).json()["bindingId"] == created.json()["bindingId"]
        conflict = client.post(path, headers=AGENT, json={**body, "requestId": "other", "number": 8})
        assert conflict.status_code == 409
        listing = client.get("/api/oporahub/reconciliation", params=scope).json()
        assert listing["items"][0]["control"]["action"] == "auto-enroll"
