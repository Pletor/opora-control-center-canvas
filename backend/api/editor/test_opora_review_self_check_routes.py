"""`POST /api/oporahub/review-jobs/self-checks`: identity, disabled feature, conflicts and success."""
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.api.editor.opora_review_self_check_routes import create_review_self_check_router
from backend.app.factory import create_app
from backend.canvas.test_opora_execution_pull_requests import SHA
from backend.canvas.test_opora_execution_pull_requests import world_fixture as world  # noqa: F401
from backend.canvas.test_opora_review_gate_fixtures import config, use
from backend.canvas.test_opora_review_jobs import review_fixture as review  # noqa: F401

PATH = "/api/oporahub/review-jobs/self-checks"


def client_for(review, value):  # noqa: F811
    use(review, value)
    app = FastAPI()

    @app.middleware("http")
    async def identity(request: Request, call_next):
        actor = request.headers.get("x-actor", "")
        request.state.actor, request.state.agent = (actor or None), request.headers.get("x-agent")
        return await call_next(request)

    app.include_router(create_review_self_check_router(review["service"], review["jobs"]))
    return TestClient(app)


def body(review, head=SHA):  # noqa: F811
    return {**review["scope"], "executionId": review["record"]["executionId"],
            "selfChecks": {"headSha": head, "checks": [{"name": "tests", "command": "pytest", "exitCode": 0,
                                                        "status": "passed"}]}}


def test_self_check_route_contract(review):  # noqa: F811
    client = client_for(review, config(self_checks={"required": ["tests"]}))
    agent = {"x-actor": "agent", "x-agent": "worker"}
    assert client.post(PATH, json=body(review)).status_code == 428
    assert client.post(PATH, headers={"x-actor": "agent"}, json=body(review)).status_code == 428
    wrong = client.post(PATH, headers=agent, json=body(review, "d" * 40))
    assert wrong.status_code == 409 and wrong.json()["code"] == "review_conflict"
    done = client.post(PATH, headers=agent, json=body(review))
    assert done.status_code == 200 and done.json()["status"]["status"] == "ok"
    use(review, {**config(), "enabled": False})
    disabled = client.post(PATH, headers=agent, json=body(review))
    assert disabled.status_code == 409 and disabled.json()["code"] == "review_jobs_disabled"


def test_route_is_registered_in_the_app(tmp_path, monkeypatch):
    monkeypatch.setenv("OPORA_RECONCILIATION_WORKER", "0")
    monkeypatch.setenv("OPORA_EXECUTION_PR_WORKER", "0")
    monkeypatch.setenv("OPORA_REVIEW_JOBS", "0")
    origin = "http://127.0.0.1:8740"
    with TestClient(create_app(tmp_path / "data"), base_url=origin) as client:
        response = client.post(PATH, headers={"origin": origin, "X-Opora-Actor": "agent; name=worker"},
                               json={"project": "p", "workspace": "w"})
    assert response.status_code == 409 and response.json()["code"] == "review_jobs_disabled"
