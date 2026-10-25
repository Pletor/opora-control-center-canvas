from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.api.editor import harness_verifier_routes as routes


def test_reference_only_bounded_route_does_not_accept_worker_observations(monkeypatch):
    calls = []
    class Verifier:
        def __init__(self, canvas):
            pass
        def verify(self, payload):
            calls.append(payload)
            if set(payload) != {"reference"}:
                raise ValueError("invalid request")
            return {"report": None}
    monkeypatch.setattr(routes, "HarnessVerifier", Verifier)
    app = FastAPI()
    @app.middleware("http")
    async def actor(request: Request, next_call):
        request.state.actor = request.headers.get("x-fixture-actor", "anonymous")
        return await next_call(request)
    app.include_router(routes.create_harness_verifier_router(object()))
    with TestClient(app) as client:
        url = "/api/oporahub/harness-verifier/requests"
        assert client.post(url, json={}).status_code == 428
        headers = {"x-fixture-actor": "agent"}
        assert client.post(url, content='{"reference":1,"reference":2}', headers=headers).status_code == 409
        assert client.post(url, content="x" * 4097, headers=headers).status_code == 413
        assert not calls
        assert client.post(url, json={"reference": 1}, headers=headers).json() == {"report": None}
        assert client.post(url, json={"report": {"outcome": "passed"}}, headers=headers).status_code == 409
