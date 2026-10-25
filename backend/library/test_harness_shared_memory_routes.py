"""Only publication references cross the shared-memory HTTP boundary."""
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.api.editor.harness_shared_memory_routes import create_harness_shared_memory_router
from backend.library import harness_shared_memory as shared


def test_actor_body_bounds_and_reference_only_dispatch(monkeypatch):
    calls = []
    monkeypatch.setattr(shared, "enqueue", lambda canvas, publication: calls.append(publication) or {"state": "pending"})
    app = FastAPI()
    @app.middleware("http")
    async def actor(request: Request, next_call):
        request.state.actor = request.headers.get("test-actor")
        return await next_call(request)
    app.include_router(create_harness_shared_memory_router(object()), prefix="/api/oporahub")
    path = "/api/oporahub/harness-shared-memory/publish"
    with TestClient(app) as client:
        assert client.post(path, json={"publication": "p"}).status_code == 428
        headers = {"test-actor": "agent"}
        for body in [{"publication": "p", "text": "private"}, {"publication": "p", "uri": "viking://private"}, []]:
            assert client.post(path, json=body, headers=headers).status_code == 409
        assert client.post(path, content=b"x" * 4097, headers=headers).status_code == 413
        assert client.post(path, content='{"publication":"p","publication":"q"}', headers=headers).status_code == 409
        assert client.post(path, json={"publication": "p"}, headers=headers).json() == {"state": "pending"}
    assert calls == ["p"]


def test_recall_does_not_reflect_remote_error_content(monkeypatch):
    def unavailable(*_):
        raise ValueError("secret remote content")
    monkeypatch.setattr(shared, "recall", unavailable)
    app = FastAPI()
    @app.middleware("http")
    async def actor(request: Request, next_call):
        request.state.actor = "agent"
        return await next_call(request)
    app.include_router(create_harness_shared_memory_router(object()))
    with TestClient(app) as client:
        response = client.post("/harness-shared-memory/recall", json={"publication": "p"})
        assert response.status_code == 409
        assert "secret" not in response.text
