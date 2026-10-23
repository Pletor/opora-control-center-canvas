"""Factory wiring of the agent-state document and its cheap conditional polling."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_opora_changesets import legacy_save
from backend.canvas.test_opora_changesets import service as service  # noqa: PLC0414

PARAMS = {"project": "draft", "workspace": "draft"}


def test_agent_state_etag_returns_304_until_the_body_changes(service):
    legacy_save(service)
    app = create_app(service.root)
    with TestClient(app, base_url="http://127.0.0.1:8740") as client:
        first = client.get("/api/oporahub/agent-state", params=PARAMS)
        assert first.status_code == 200, first.text
        tag = first.headers["etag"]
        assert first.json()["schemaVersion"] == 1
        cached = client.get("/api/oporahub/agent-state", params=PARAMS, headers={"If-None-Match": tag})
        assert cached.status_code == 304 and cached.headers["etag"] == tag and not cached.content
        legacy_save(service, goal="Changed working goal")
        changed = client.get("/api/oporahub/agent-state", params=PARAMS, headers={"If-None-Match": tag})
        assert changed.status_code == 200 and changed.headers["etag"] != tag


def test_agent_state_rejects_invalid_scope(service):
    app = create_app(service.root)
    with TestClient(app, base_url="http://127.0.0.1:8740") as client:
        response = client.get("/api/oporahub/agent-state", params={"project": "../x", "workspace": "draft"})
        assert response.status_code == 409 and response.json()["code"] == "agent_state_unavailable"


def test_agent_state_cards_offset_is_its_own_etag_and_must_not_be_negative(service):
    legacy_save(service)
    app = create_app(service.root)
    with TestClient(app, base_url="http://127.0.0.1:8740") as client:
        first = client.get("/api/oporahub/agent-state", params=PARAMS)
        later = client.get("/api/oporahub/agent-state", params={**PARAMS, "cardsOffset": 100})
        assert later.status_code == 200 and later.json()["cards"] == [] and later.json()["truncated"] is True
        assert later.json()["actions"] == first.json()["actions"]
        assert later.headers["etag"] != first.headers["etag"]
        cached = client.get("/api/oporahub/agent-state", params={**PARAMS, "cardsOffset": 100},
                            headers={"If-None-Match": later.headers["etag"]})
        assert cached.status_code == 304
        bad = client.get("/api/oporahub/agent-state", params={**PARAMS, "cardsOffset": -1})
        assert bad.status_code == 422
