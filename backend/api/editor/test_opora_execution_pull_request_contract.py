"""Wire contract with agent-office `src/server/opora/pull-request-handoff.ts` (`PullRequestHandoff.link`).

OFFICE_REQUEST is the request agent-office actually sends, captured verbatim from its `link()` with a
recording transport (placeholders EXEC_ID / PROJECT / WORKSPACE / TOKEN / epoch 1; the branch comes
from `handoffBranch('card', 'EXEC_ID')` and requestId from `linkRequestId`). If either side changes
the shape, this test breaks. agent-office reads 2xx as linked, 404 as not deployed, 409 as conflict.
"""
import json

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.test_canvas_service import managed_fixture
from backend.canvas.test_opora_execution_pull_requests import pr
from backend.canvas.test_opora_review_fixtures import setup
from backend.integrations.github_pr_link_reader import GitHubPullRequestLinkReader

OFFICE_REQUEST = {
    "url": "http://127.0.0.1:8740/api/oporahub/executions/EXEC_ID/pull-request",
    "method": "POST",
    "headers": {"Accept": "application/json", "Content-Type": "application/json",
                "Origin": "http://127.0.0.1:8740", "X-Opora-Actor": "agent; name=worker"},
    "body": '{"project":"PROJECT","workspace":"WORKSPACE","token":"TOKEN","epoch":1,'
            '"requestId":"da8f8d70-d072-506f-bd12-2aa43aca6b70","repository":"owner/repo","number":7,'
            '"headRef":"opora/card/EXEC_ID","headSha":"cccccccccccccccccccccccccccccccccccccccc"}',
}
ORIGIN = "http://127.0.0.1:8740"


def office(record):
    """The captured request with this execution's real identity and credentials substituted."""
    body = json.loads(OFFICE_REQUEST["body"])
    assert list(body) == ["project", "workspace", "token", "epoch", "requestId", "repository", "number",
                          "headRef", "headSha"]
    body.update(project=record["project"], workspace=record["workspace"], token=record["token"],
                epoch=record["epoch"], headRef=body["headRef"].replace("EXEC_ID", record["executionId"]))
    path = OFFICE_REQUEST["url"].removeprefix(ORIGIN).replace("EXEC_ID", record["executionId"])
    return path, dict(OFFICE_REQUEST["headers"]), body


def test_canvas_accepts_the_exact_agent_office_link_request(tmp_path, monkeypatch):
    monkeypatch.setenv("OPORA_RECONCILIATION_WORKER", "0")
    monkeypatch.setenv("OPORA_EXECUTION_PR_WORKER", "0")
    monkeypatch.setattr(GitHubPullRequestLinkReader, "pull_request", lambda self, repository, number: pr(number))
    fixture, project = managed_fixture(tmp_path)
    fixture.close()
    app = create_app(tmp_path / "data")
    with TestClient(app, base_url=ORIGIN) as client:
        service = app.state.service
        scope = setup(service, project["id"])
        scope = {"project": scope["project"], "workspace": scope["workspace"]}
        executions = ExecutionResults(service)
        context = executions.context(**scope, node="card")
        record = executions.claim({**scope, "nodeId": "card", "requestId": "claim", "ttlSeconds": 60,
                                   "expectedAcceptedHead": context["acceptedHead"],
                                   "expectedContextVersion": context["contextVersion"]}, "agent:worker")
        # agent-office links only after the worker's result receipt is stored; the lease may be gone.
        executions.submit(record["executionId"], {**scope, "token": record["token"], "epoch": record["epoch"],
                                                  "requestId": "result", "result": {"summary": "Done"}})
        path, headers, body = office({**record, **scope})
        client.cookies.clear()

        linked = client.post(path, headers=headers, content=json.dumps(body, separators=(",", ":")))
        assert linked.status_code == 200, linked.text
        assert linked.json()["executionId"] == record["executionId"] and linked.json()["cardId"] == "card"
        assert linked.json()["headSha"] == body["headSha"]  # headRef is re-read from GitHub on enrollment
        assert linked.json()["enrollment"] == "enrolled" and "token" not in linked.text

        # The office retries the same commit with the same requestId: idempotent 200, same link.
        again = client.post(path, headers=headers, content=json.dumps(body, separators=(",", ":")))
        assert again.status_code == 200 and again.json()["bindingId"] == linked.json()["bindingId"]
        # Wrong epoch / different PR → 409 (office: "conflict", not retried); unknown execution → 409.
        assert client.post(path, headers=headers, json={**body, "epoch": body["epoch"] + 1}).status_code == 409
        assert client.post(path, headers=headers, json={**body, "requestId": "other", "number": 8}).status_code == 409
        # Without the office's actor header the route refuses identity-less writes (428).
        assert client.post(path, headers={"Origin": ORIGIN}, json=body).status_code == 428
