"""Factory wiring and node brief navigation use the exact scope without recursion."""
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.test_opora_changesets import legacy_save
from backend.canvas.test_opora_changesets import service as service  # noqa: PLC0414


def test_real_factory_process_and_brief_have_live_scoped_navigation(service):
    legacy_save(service)
    app = create_app(service.root)
    with TestClient(app, base_url="http://127.0.0.1:8740") as client:
        response = client.get("/api/oporahub/process", params={"project": "draft", "workspace": "draft", "nodeId": "a"})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["schema"] == "opora.process-sync/1"
        assert result["items"][0]["nodeId"] == "a"
        brief = client.get(result["items"][0]["links"]["brief"])
        assert brief.status_code == 200, brief.text
        navigation = brief.json()["processSync"]
        assert navigation["live"]
        assert navigation["process"] == "/api/oporahub/process?project=draft&workspace=draft&nodeId=a"
        assert navigation["links"]["context"] == result["items"][0]["links"]["context"]
        assert client.get(navigation["links"]["proposalContext"]).status_code == 200
        assert client.get("/api/oporahub/process?project=draft&workspace=draft&nodeId=missing").status_code == 409
