"""Actual factory/middleware: identity, worker lease endpoints, human-only operations and gates."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.test_opora_execution_pull_requests import SHA, pr
from backend.canvas.test_opora_review_fixtures import setup
from backend.integrations.github_pr_base_reader import GitHubPullRequestBaseReader
from backend.integrations.github_pr_change_reader import GitHubPullRequestChangeReader
from backend.integrations.github_pr_link_reader import GitHubPullRequestLinkReader
from database.schema.opora_review_job_schema import TABLES
from database.schema.project_schema import PROJECT_TABLES

ORIGIN = "http://127.0.0.1:8740"
AGENT = {"origin": ORIGIN, "X-Opora-Actor": "agent; name=worker"}
BASE = "/api/oporahub/review-jobs"


def change(self, repository, number, head):
    return {"complete": True, "baseSha": "b" * 40, "files": [{"path": "src/a.py", "additions": 1, "deletions": 0}]}


def test_worker_contract_over_http(tmp_path, monkeypatch):
    monkeypatch.setenv("OPORA_RECONCILIATION_WORKER", "0")
    monkeypatch.setenv("OPORA_EXECUTION_PR_WORKER", "0")
    monkeypatch.setenv("OPORA_REVIEW_JOBS", "0")
    monkeypatch.setattr(GitHubPullRequestLinkReader, "pull_request", lambda self, repository, number: pr(number))
    monkeypatch.setattr(GitHubPullRequestChangeReader, "change", change)
    monkeypatch.setattr(GitHubPullRequestBaseReader, "base", lambda self, *_: {"complete": False, "error": "offline"})
    from backend.canvas.test_canvas_service import managed_fixture
    fixture, project = managed_fixture(tmp_path)
    fixture.close()
    app = create_app(tmp_path / "data")
    with TestClient(app, base_url=ORIGIN) as client:
        assert set(TABLES) <= PROJECT_TABLES.keys()
        service = app.state.service
        scope = setup(service, project["id"])
        scope = {"project": scope["project"], "workspace": scope["workspace"]}
        executions = ExecutionResults(service)
        context = executions.context(**scope, node="card")
        record = executions.claim({**scope, "nodeId": "card", "requestId": "claim", "ttlSeconds": 60,
                                   "expectedAcceptedHead": context["acceptedHead"],
                                   "expectedContextVersion": context["contextVersion"]}, "agent:worker")
        link = {**scope, "token": record["token"], "epoch": record["epoch"], "requestId": "link",
                "repository": "owner/repo", "number": 7, "headRef": "feature", "headSha": SHA}
        assert client.post(f"/api/oporahub/executions/{record['executionId']}/pull-request", headers=AGENT,
                           json=link).status_code == 200
        claim = {**scope, "requestId": "c1", "ttlSeconds": 60, "role": "finder"}
        disabled = client.post(BASE + "/claim", headers=AGENT, json=claim)
        assert disabled.status_code == 409 and disabled.json()["code"] == "review_jobs_disabled"
        monkeypatch.setenv("OPORA_REVIEW_JOBS", "1")
        client.cookies.clear()
        assert client.post(BASE + "/claim", headers={"origin": ORIGIN}, json=claim).status_code == 428
        task = client.post(BASE + "/claim", headers=AGENT, json=claim).json()["task"]
        assert task["role"] == "finder" and task["job"]["headSha"] == SHA and task["job"]["riskTier"] == "low"
        path = f"{BASE}/{task['reviewJobId']}/tasks/{task['taskId']}"
        held = {**scope, "token": task["token"], "epoch": task["epoch"]}
        assert client.post(path + "/heartbeat", headers=AGENT, json={**held, "ttlSeconds": 90}).status_code == 200
        assert client.post(path + "/heartbeat", headers=AGENT,
                           json={**held, "epoch": 9, "ttlSeconds": 90}).status_code == 409
        finding = {"path": "src/a.py", "line": 1, "severity": "important", "fingerprint": "fp-aaaaaaaa",
                   "title": "Bug", "rationale": "Why."}
        submitted = client.post(path + "/submit", headers=AGENT,
                                json={**held, "requestId": "s1", "submission": {"findings": [finding]}})
        assert submitted.status_code == 200 and submitted.json()["state"] == "submitted"
        for index in (2, 3):
            other = client.post(BASE + "/claim", headers=AGENT,
                                json={**scope, "requestId": f"c{index}", "ttlSeconds": 60}).json()["task"]
            client.post(f"{BASE}/{other['reviewJobId']}/tasks/{other['taskId']}/submit", headers=AGENT,
                        json={**scope, "token": other["token"], "epoch": other["epoch"], "requestId": "s",
                              "submission": {"findings": [finding]}})
        for index in (1, 2, 3):
            voter = client.post(BASE + "/claim", headers=AGENT,
                                json={**scope, "requestId": f"v{index}", "ttlSeconds": 60, "role": "voter"}).json()["task"]
            votes = [{"candidateId": item["candidateId"], "verdict": "confirm"} for item in voter["candidates"]]
            response = client.post(f"{BASE}/{voter['reviewJobId']}/tasks/{voter['taskId']}/submit", headers=AGENT,
                                   json={**scope, "token": voter["token"], "epoch": voter["epoch"], "requestId": "v",
                                         "submission": {"votes": votes}})
            assert response.status_code == 200, response.text
        listing = client.get(BASE, headers=AGENT, params=scope).json()
        code = next(job for job in listing["jobs"] if job["kind"] == "code")  # + security `not_required` marker
        assert code["phase"] == "completed" and task["token"] not in str(listing)
        [posted] = listing["findings"]
        gates = client.get(BASE + "/gates", headers=AGENT, params=scope).json()["items"]
        assert gates[0]["reviewGate"]["status"] == "blocked" and gates[0]["reviewGate"]["openImportant"] == 1
        resolve = f"{BASE}/findings/{posted['findingId']}/resolve"
        denied = client.post(resolve, headers=AGENT, json={**scope, "reason": "No."})
        assert denied.status_code == 403 and denied.json()["code"] == "human_required"
        assert client.post(f"{BASE}/findings/rf_{'0' * 24}/resolve", headers=AGENT,
                           json={**scope, "reason": "x"}).status_code == 404
        decision = client.post(BASE + "/decisions", headers=AGENT, json={
            **scope, "repository": "owner/repo", "number": 7, "headSha": SHA, "reason": "x"})
        assert decision.status_code == 403
        state = client.get("/api/oporahub/agent-state", headers=AGENT, params=scope).json()
        assert next(item for item in state["stages"] if item["id"] == "review")["reason"] == "review_gate_blocked"
        assert "ai_review" not in [gap["id"] for gap in state["gaps"]]
