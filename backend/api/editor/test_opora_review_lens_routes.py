"""`POST /api/oporahub/review-jobs/lens` and `GET /api/oporahub/review-lens`: identity, conflicts, the card read."""
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.api.editor.opora_review_lens_routes import create_review_lens_router
from backend.app.factory import create_app
from backend.canvas.test_opora_execution_pull_requests import SHA
from backend.canvas.test_opora_execution_pull_requests import world_fixture as world  # noqa: F401
from backend.canvas.test_opora_review_gate_fixtures import config, use
from backend.canvas.test_opora_review_jobs import review_fixture as review  # noqa: F401

POST, GET = "/api/oporahub/review-jobs/lens", "/api/oporahub/review-lens"
AGENT = {"x-actor": "agent", "x-agent": "worker"}


def client_for(review):  # noqa: F811
    use(review, config())
    app = FastAPI()

    @app.middleware("http")
    async def identity(request: Request, call_next):
        actor = request.headers.get("x-actor", "")
        request.state.actor, request.state.agent = (actor or None), request.headers.get("x-agent")
        return await call_next(request)

    app.include_router(create_review_lens_router(review["service"], review["jobs"]))
    return TestClient(app)


def body(review, head=SHA):  # noqa: F811
    return {**review["scope"], "executionId": review["record"]["executionId"],
            "lens": {"url": "https://github.com/owner/repo/raw/" + "e" * 40 + "/.pr-lens/o.svg", "prNumber": 7,
                     "headSha": head, "validatedAt": "2026-10-22T11:50:00Z", "spec": {"kind": "graph", "nodes": []}}}


def test_lens_route_contract(review):  # noqa: F811
    client = client_for(review)
    query = {**review["scope"], "nodeId": "card"}
    assert client.post(POST, json=body(review)).status_code == 428
    assert client.get(GET, params=query).status_code == 428
    assert client.get(GET, headers=AGENT, params=query).json() == {"nodeId": "card", "lens": None}
    wrong = client.post(POST, headers=AGENT, json=body(review, "d" * 40))
    assert wrong.status_code == 409 and wrong.json()["code"] == "review_conflict"
    done = client.post(POST, headers=AGENT, json=body(review))
    assert done.status_code == 200 and done.json()["recorded"] is True
    read = client.get(GET, headers=AGENT, params=query).json()
    assert read["current"] is True and read["by"] == "agent:worker" and read["lens"]["spec"] == {"kind": "graph", "nodes": []}
    assert client.get(GET, headers=AGENT, params={**query, "nodeId": "bad id!"}).status_code == 400


def test_routes_are_registered_in_the_app(tmp_path, monkeypatch):
    monkeypatch.setenv("OPORA_RECONCILIATION_WORKER", "0")
    monkeypatch.setenv("OPORA_EXECUTION_PR_WORKER", "0")
    monkeypatch.setenv("OPORA_REVIEW_JOBS", "0")
    origin = "http://127.0.0.1:8740"
    with TestClient(create_app(tmp_path / "data"), base_url=origin) as client:
        response = client.post(POST, headers={"origin": origin, "X-Opora-Actor": "agent; name=worker"},
                               json={"project": "p", "workspace": "w"})
    assert response.status_code == 409 and response.json()["code"] == "review_conflict"
