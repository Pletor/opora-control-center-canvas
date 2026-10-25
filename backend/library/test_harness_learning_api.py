"""Read-only registered API returns scoped, bounded native projections, not execution text."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.editor.harness_learning_routes import create_harness_learning_router


def test_read_route_is_scoped_bounded_and_has_no_verification_write(learning_run):
    service, _, _, _ = learning_run
    app = FastAPI()
    app.include_router(create_harness_learning_router(service))
    with TestClient(app) as client:
        base = "/api/oporahub/harness-learning"
        result = client.get(base, params={"project": "draft", "workspace": "draft"})
        assert result.status_code == 200
        value = result.json()
        assert value["authority"] == "native-outbox-projection" and len(value["cohorts"]) == 2
        assert "content" not in result.text and "token" not in result.text.replace('"tokens":null', '')
        assert client.post(base, json={"tier": "verified", "outcome": "pass"}).status_code == 405
        assert client.get(base, params={"project": "draft", "workspace": "draft", "limit": 101}).status_code == 422
        assert client.get(base, params={"project": "missing", "workspace": "draft"}).status_code == 404
        assert client.get(base, params={"project": "draft", "workspace": "other"}).json()["cohorts"] == []
        assert client.get(base, params={"project": "draft", "workspace": "draft", "resource": "rule:other"}).json()["cohorts"] == []
        deliveries = "/api/oporahub/harness-memory"
        assert client.get(deliveries, params={"project": "draft", "workspace": "draft"}).json()["items"] == []
        assert client.post(deliveries, json={"state": "submitted"}).status_code == 405
        assert client.get(deliveries, params={"project": "missing", "workspace": "draft"}).status_code == 404
        assert client.get(deliveries, params={"project": "draft", "workspace": "draft", "limit": 101}).status_code == 422
