"""Actual boundary denies token leakage while keeping genuine local UI reads."""
import pytest
from fastapi.testclient import TestClient
from backend.app.factory import create_app
from backend.brain_opora.determinism import tokens, gate_setting
from backend.flow import workflows

ORIGIN = "http://127.0.0.1:8740"


@pytest.mark.parametrize("gate_on", [False, True])
def test_token_scope_overrides_cookie_and_gate_switch(tmp_path, gate_on):
    app = create_app(tmp_path / "data")
    service = app.state.service
    with TestClient(app, base_url=ORIGIN) as client:
        other = service.project_hub.empty_project({"name": "Foreign", "confirmed": True})["id"]
        gate_setting.write(service, {"project": "draft", "enabled": gate_on})
        identifier, token = tokens.issue_heart(service, "draft", "draft")
        # TestClient carries the real human UI cookie. Supplied token must still constrain it.
        auth = {"origin": ORIGIN, tokens.HEADER: token}
        assert client.get("/api/view", params={"project": other, "workspace": "draft"}).status_code == 200
        response = client.get("/api/view", params={"project": other, "workspace": "draft"}, headers=auth)
        assert response.status_code == 403 and response.json()["code"] == "gate_scope"
        assert client.get("/api/view", params={"project": "draft", "workspace": "draft"}, headers=auth).status_code == 200
        assert client.get("/api/bootstrap", params={"project": "draft"}, headers=auth).status_code == 403
        assert client.get("/api/bootstrap").status_code == 200
        denied = client.post("/api/brain/canvas/invoke", headers=auth, json={"project": "draft", "workspace": "other",
            "capability": "canvas_routes.view", "input": {}})
        assert denied.status_code == 403
        # Invalid token is not ignored because a valid human cookie also exists.
        assert client.get("/api/health", headers={tokens.HEADER: "invalid"}).status_code == 401
        tokens.revoke(service, "draft", identifier)
        assert client.get("/api/view", params={"project": "draft", "workspace": "draft"}, headers=auth).status_code == 401


def test_id_only_foreign_flow_read_rejected_before_native_content(tmp_path):
    app = create_app(tmp_path / "data")
    service = app.state.service
    own = service.project_hub.empty_project({"name": "Own", "confirmed": True})["id"]
    other = service.project_hub.empty_project({"name": "Foreign", "confirmed": True})["id"]
    _, token = tokens.issue_heart(service, own, "draft")
    with service.registry_lock:
        foreign = workflows.create_workflow(service.db, "heart", "Secret workflow", other)
    with TestClient(app, base_url=ORIGIN) as client:
        path = "/api/flow/workflows/" + foreign["id"] + "/versions"
        for query in ({}, {"project": own}):
            response = client.get(path, params=query, headers={tokens.HEADER: token})
            assert response.status_code == 403
            assert "Secret workflow" not in response.text
        assert client.get(path).status_code == 200
        # ID-only writes must not rely on a project gate that can be disabled.
        response = client.post(path, headers={tokens.HEADER: token, "origin": ORIGIN},
                               json={"graph": {"nodes": [], "edges": []}})
        assert response.status_code == 403 and response.json()["code"] == "gate_scope"
