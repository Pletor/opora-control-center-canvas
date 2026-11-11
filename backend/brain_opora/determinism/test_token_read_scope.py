"""Legacy token constraints do not depend on the project's write-gate setting."""
import json

import pytest
from backend.canvas.canvas_service import CanvasService
from backend.brain_opora.determinism import tokens, brain_files
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.brain_opora.determinism.token_read_scope import enforce
from backend.flow import workflows


@pytest.fixture
def source(tmp_path):
    service = CanvasService(tmp_path / "data")
    identifier, token = tokens.issue_heart(service, "draft", "draft")
    return service, identifier, token


def test_no_token_keeps_local_reads_but_supplied_invalid_or_revoked_fails(source):
    service, identifier, token = source
    assert enforce(service, "GET", "/api/bootstrap", None, {}) is None
    with pytest.raises(GateError) as error:
        enforce(service, "GET", "/api/view", "invalid", {"project": "draft"})
    assert error.value.status == 401
    tokens.revoke(service, "draft", identifier)
    with pytest.raises(GateError) as error:
        enforce(service, "HEAD", "/api/health", token, {})
    assert error.value.status == 401


@pytest.mark.parametrize("query,body", [({"project": "foreign"}, {}),
    ({"project": "draft"}, {"project": "foreign"}), ({"project": "draft", "of": "foreign"}, {}),
    ({"project": "draft", "workspace": "other"}, {}), ({"project": "draft"}, {"workspace": "other"})])
def test_foreign_scope_rejected_even_with_gate_off(source, query, body):
    service, _, token = source
    with pytest.raises(GateError) as error:
        enforce(service, "GET", "/api/view", token, query, body)
    assert error.value.status == 403


def test_scoped_reads_match_paths_and_unknown_unscoped_routes_fail_closed(source):
    service, identifier, token = source
    for path in ("/api/view", "/api/research/cards/abc", "/api/brain/canvas/capabilities/canvas_routes.view"):
        assert enforce(service, "GET", path, token, {"project": "draft", "workspace": "draft"})["id"] == identifier
    for path, query in (("/api/view", {}), ("/api/unknown", {"project": "draft"}),
                        ("/api/bootstrap", {"project": "draft"})):
        with pytest.raises(GateError):
            enforce(service, "GET", path, token, query)


def test_main_to_saved_active_delegation_and_metadata_are_explicit(source):
    service, _, _ = source
    _, main = tokens.issue_heart(service, "draft", "main")
    brain = brain_files.brain_dir(service, "draft")
    brain.mkdir(parents=True, exist_ok=True)
    (brain / brain_files.ACTIVE).write_text(json.dumps({"workspace": "draft"}), encoding="utf-8")
    assert enforce(service, "GET", "/api/view", main, {"project": "draft", "workspace": "draft"})
    assert enforce(service, "POST", "/api/canvas-plan", main, {}, {"project": "draft", "workspace": "draft"})
    _, bound = tokens.issue_heart(service, "draft", "draft")
    assert enforce(service, "GET", "/api/view", bound, {"project": "draft", "workspace": "main"})
    with pytest.raises(GateError):
        enforce(service, "GET", "/api/node-text", bound, {"project": "draft", "workspace": "main"})


def test_flow_id_owner_beats_spoofed_query_project(source):
    service, _, token = source
    foreign_project = service.project_hub.empty_project({"name": "Foreign", "confirmed": True})["id"]
    own_project = service.project_hub.empty_project({"name": "Own", "confirmed": True})["id"]
    _, token = tokens.issue_heart(service, own_project, "draft")
    with service.registry_lock:
        foreign = workflows.create_workflow(service.db, "heart", "Foreign", foreign_project)
        own = workflows.create_workflow(service.db, "heart", "Own", own_project)
    for query in ({}, {"project": own_project}):
        with pytest.raises(GateError) as error:
            enforce(service, "GET", "/api/flow/workflows/" + foreign["id"] + "/versions", token, query)
        assert error.value.status == 403
    assert enforce(service, "GET", "/api/flow/workflows/" + own["id"] + "/versions", token, {})


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_public_brain_pin_read_with_worker_token_preserves_identity_and_scope(source, method):
    service, _, _ = source
    worker = tokens.issue_worker(service, "draft", "draft", {"name": "office-pin-test"})
    token = worker["token"]
    path = "/api/brain-registry/pins/ponytail@a5bfdccd69db.zip"
    for query in ({}, {"project": "draft", "workspace": "draft"}):
        assert enforce(service, method, path, token, query)["id"] == worker["sessionId"]
    for query in ({"project": "foreign"}, {"workspace": "foreign"}):
        with pytest.raises(GateError) as error:
            enforce(service, method, path, token, query)
        assert error.value.status == 403
    with pytest.raises(GateError) as error:
        enforce(service, method, path, "invalid", {})
    assert error.value.status == 401
    tokens.revoke(service, "draft", worker["sessionId"])
    with pytest.raises(GateError) as error:
        enforce(service, method, path, token, {})
    assert error.value.status == 401


@pytest.mark.parametrize("path", ["/api/brain-registry/artifacts", "/api/brain-registry/pins",
    "/api/brain-registry/pins/ponytail@a5bfdccd69db.zip/extra",
    "/api/brain-registry/pins/ponytail@a5bfdccd69db.txt",
    "/api/brain-registry/pins/ponytail@a5bfdcc.zip"])
def test_public_pin_read_does_not_open_other_registry_reads(source, path):
    service, _, token = source
    with pytest.raises(GateError) as error:
        enforce(service, "GET", path, token, {"project": "draft"})
    assert error.value.status == 403
