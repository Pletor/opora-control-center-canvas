import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app


@pytest.mark.parametrize("length", [100, 101, 120])
def test_saved_model_identifier_is_accepted_by_runtime_validation(tmp_path, length):
    app = create_app(tmp_path)
    with TestClient(app, base_url="http://127.0.0.1:8740") as client:
        settings = client.get("/api/project-settings?project=draft").json()["settings"]
        settings.update(goal="Validation parity", model="m" * length)
        response = client.post("/api/project-settings", headers={"origin": "http://127.0.0.1:8740"}, json={"project": "draft", "expected_revision": 0, "name": "Test", "settings": settings})
        assert response.status_code == 200
        context = client.get("/api/llm/preview?project=draft&workspace=draft").json()["context"]
        assert app.state.plan_runs._validate_settings(context)["model"] == "m" * length
