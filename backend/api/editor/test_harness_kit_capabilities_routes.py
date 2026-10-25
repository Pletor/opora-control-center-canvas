from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.editor.harness_learning_routes import create_harness_learning_router
from backend.library.harness_kit import validate_kit


def client():
    app = FastAPI()
    app.include_router(create_harness_learning_router(SimpleNamespace(project_exists=lambda project: project == "p")))
    return TestClient(app)


def test_advertised_formats_are_accepted_and_do_not_grant_execution():
    with client() as http:
        response = http.get("/api/oporahub/harness-kit-capabilities?project=p&workspace=w")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    value = response.json()
    assert value["schema"] == "harness.kit-capabilities/1"
    assert value["scope"] == {"project": "p", "workspace": "w"}
    assert value["acceptedKitSchemas"] == ["harness.kit/1", "harness.kit/2"]
    assert value["contextProtocolVersion"] == 2
    assert value["limits"] == {"resources": 24, "bytes": 96 * 1024}
    assert value["evidence"] == "installed-acceptance-validator"
    assert value["executionAdaptersVerified"] is False
    assert value["permissionsGranted"] is False
    assert value["promotionAllowed"] is False
    for schema in value["acceptedKitSchemas"]:
        kit = {"schema": schema, "problems": ["build"], "resources": []}
        if schema == "harness.kit/2":
            kit["selection"] = {"schema": value["selectionSchema"], "policy": "harness.recommendation/1",
                                "problem": "build", "profileRevision": None, "declaredCapabilities": [],
                                "evidence": "caller-declared-selection", "entries": []}
        validate_kit(kit)


def test_discovery_rejects_invalid_scope_and_missing_project():
    with client() as http:
        assert http.get("/api/oporahub/harness-kit-capabilities?project=p").status_code == 422
        invalid = http.get("/api/oporahub/harness-kit-capabilities?project=p&workspace=")
        assert invalid.status_code == 422
        missing = http.get("/api/oporahub/harness-kit-capabilities?project=absent&workspace=w")
        assert missing.status_code == 404
        assert missing.headers["cache-control"] == "no-store"
        assert "acceptedKitSchemas" not in missing.json()
