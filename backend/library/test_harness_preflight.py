"""Preflight exposes exact accepted kit content, not an execution capability."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.editor.harness_learning_routes import create_harness_learning_router
from backend.canvas.test_opora_changesets import SCOPE, accept, legacy_save
from backend.canvas.test_opora_execution_context import claimed, prepared, sparse
from backend.canvas.test_opora_graph_initial import empty_graphs
from backend.library.harness_preflight import preview
from backend.library.test_harness_kit import kit, propose_kit

__all__ = ["empty_graphs", "sparse"]


def request(sparse):
    context = prepared(sparse)
    return {**SCOPE, "nodeId": sparse[2]["a"], "expectedAcceptedHead": context["acceptedHead"],
            "expectedContextVersion": context["contextVersion"]}


def test_exact_target_kit_and_idempotent_preview_create_no_execution(sparse):
    canvas = sparse[0].service
    proposed, head = propose_kit(sparse, kit())
    accept(canvas, proposed, head)
    payload = request(sparse)
    result = preview(canvas, payload)
    assert result == preview(canvas, payload)
    assert result["kit"] == kit()
    assert not result["runnerReadinessVerified"] and not result["executionAuthority"]
    assert not result["permissionsGranted"]
    assert not {"token", "pin", "snapshot", "documents", "secret"}.intersection(result)
    for table in ("opora_execution_context_pins", "opora_execution_epochs", "card_leases", "opora_executions"):
        assert canvas.db_for("draft").execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    result["kit"]["resources"].clear()
    assert preview(canvas, payload)["kit"] == kit()


def test_missing_kit_is_explicit_and_changed_accepted_or_working_context_refused(sparse):
    canvas = sparse[0].service
    old = request(sparse)
    assert preview(canvas, old)["kit"] is None
    proposed, head = propose_kit(sparse, kit())
    accept(canvas, proposed, head)
    with pytest.raises(ValueError):
        preview(canvas, old)
    current = request(sparse)
    legacy_save(canvas, sparse[2]["a"])
    with pytest.raises(ValueError):
        preview(canvas, current)


def test_preview_digest_matches_actual_claim_including_predecessor_handoff(sparse):
    payload = request(sparse)
    result = preview(sparse[0].service, payload)
    lease = claimed(sparse)
    assert "handoff" in lease["assignment"]
    assert result["assignmentDigest"] == lease["assignmentDigest"]


def test_registered_route_bounds_identity_and_stale_context(sparse):
    payload = request(sparse)
    app = FastAPI()
    app.include_router(create_harness_learning_router(sparse[0].service))
    @app.middleware("http")
    async def identity(request, call_next):
        request.state.actor = request.headers.get("x-test-actor")
        return await call_next(request)
    with TestClient(app) as client:
        url = "/api/oporahub/harness-preflight"
        assert client.post(url, json=payload).status_code == 428
        headers = {"x-test-actor": "agent"}
        response = client.post(url, json=payload, headers=headers)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == preview(sparse[0].service, payload)
        assert client.post(url, content=b"x" * 4097, headers=headers).status_code == 413
        for body in ({**payload, "extra": True}, {**payload, "expectedContextVersion": "0" * 64},
                     {**payload, "nodeId": sparse[2]["b"]}, {**payload, "workspace": "foreign"}):
            assert client.post(url, json=body, headers=headers).status_code == 409
        assert client.post(url, content=b'{"project":"draft","project":"other"}', headers=headers).status_code == 409
