"""Actual factory/middleware: identity required, human-only identity writes, metrics, evals and recurring."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_opora_review_fixtures import setup
from backend.integrations.github_identity_reader import GitHubIdentityReader
from database.schema.opora_review_insight_schema import TABLES
from database.schema.project_schema import PROJECT_TABLES

ORIGIN = "http://127.0.0.1:8740"
AGENT = {"origin": ORIGIN, "X-Opora-Actor": "agent; name=worker"}
HUMAN = {"origin": ORIGIN}


def test_review_insight_contract_over_http(tmp_path, monkeypatch):
    monkeypatch.setenv("OPORA_RECONCILIATION_WORKER", "0")
    monkeypatch.setenv("OPORA_EXECUTION_PR_WORKER", "0")
    posted = []
    monkeypatch.setattr(GitHubIdentityReader, "comments", lambda self, repository, number: list(posted))
    from backend.canvas.test_canvas_service import managed_fixture
    fixture, project = managed_fixture(tmp_path)
    fixture.close()
    app = create_app(tmp_path / "data")
    with TestClient(app, base_url=ORIGIN) as client:
        assert set(TABLES) <= PROJECT_TABLES.keys()
        scope = setup(app.state.service, project["id"])
        pid = scope["project"]
        claim = {"project": pid, "name": "Martin", "githubLogin": "martin", "operator": True}
        denied = client.post("/api/oporahub/review-identities/claim", headers=AGENT, json=claim)
        assert denied.status_code == 403 and denied.json()["code"] == "human_required"
        claimed = client.post("/api/oporahub/review-identities/claim", headers=HUMAN, json=claim).json()
        path = f"/api/oporahub/review-identities/{claimed['identityId']}/verify"
        missing = client.post(path, headers=HUMAN, json={"project": pid, "number": 3})
        assert missing.status_code == 409 and missing.json()["code"] == "identity_proof_missing"
        posted.append({"id": 1, "login": "martin", "userId": 7, "userType": "User", "body": claimed["marker"],
                       "createdAt": "2026-10-21T10:00:00Z", "url": "https://x"})
        assert client.post(path, headers=AGENT, json={"project": pid, "number": 3}).status_code == 403
        verified = client.post(path, headers=HUMAN, json={"project": pid, "number": 3}).json()
        assert verified["state"] == "verified" and verified["githubUserId"] == 7
        listing = client.get("/api/oporahub/review-identities", headers=AGENT, params={"project": pid}).json()
        assert [item["state"] for item in listing["items"]] == ["verified"]
        metrics = client.get("/api/oporahub/review-metrics", headers=AGENT, params={"project": pid, "window": "7d"})
        assert metrics.status_code == 200 and metrics.json()["prsReviewed"] == 0
        assert client.get("/api/oporahub/review-metrics", headers=AGENT,
                          params={"project": pid, "window": "7w"}).status_code == 409
        export = client.get("/api/oporahub/review-evals/export.jsonl", headers=AGENT, params={"project": pid})
        assert export.status_code == 200 and export.text == "" and "ndjson" in export.headers["content-type"]
        assert client.get("/api/oporahub/review-evals", headers=AGENT, params={"project": pid}).json() == {"items": []}
        incident = client.post("/api/oporahub/review-incidents", headers=AGENT, json={
            "project": pid, "workspace": scope["workspace"], "repository": "owner/repo", "number": 7,
            "reference": "INC-1", "summary": "Outage"})
        assert incident.status_code == 404
        recurring = client.get("/api/oporahub/review-recurring", headers=AGENT, params={"project": pid}).json()
        assert recurring == {"minPrs": 3, "items": []}
        client.cookies.clear()
        assert client.get("/api/oporahub/review-metrics", headers=HUMAN, params={"project": pid}).status_code == 428
