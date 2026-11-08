"""Native writes retain identity across retries without implicitly accepting plans."""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.canvas.canvas_plan import apply_plan
from backend.canvas.canvas_service import CanvasService
from backend.canvas.payload_errors import NextStep
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN, SCOPE, plan, seed
from backend.api.editor.test_opora_changeset_routes import AGENT

BASE = "/api/oporahub/graph-proposals"


def payload(service):
    return {**SCOPE, "digest": service.view("draft", "draft")["digest"], "operationId": "test-1",
            "plan": {"nodes": [{"ref": "task", "kind": "node", "name": "Task",
                                "text": "Full task text", "spec": {"goal": "Goal"}}]}}


def receipts(service):
    return service.db_for("draft").execute("SELECT status FROM canvas_operation_receipts").fetchall()


def test_canvas_http_replay_before_stale_cas_and_actor_binding(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        body = {**SCOPE, "digest": seed(client), "operationId": "full-plan", "plan": plan()}
        first = client.post("/api/canvas-plan", headers=HEADERS, json=body)
        assert first.status_code == 200, first.text
        graph = client.get("/api/view", params=SCOPE).json()
        replay = client.post("/api/canvas-plan", headers=HEADERS, json=body)
        assert replay.json() == first.json()
        assert client.get("/api/view", params=SCOPE).json()["digest"] == graph["digest"]
        changed = deepcopy(body)
        changed["plan"]["nodes"][0]["name"] = "Different"
        for candidate, headers in [(changed, HEADERS), (body, AGENT)]:
            response = client.post("/api/canvas-plan", headers=headers, json=candidate)
            assert response.status_code == 409, response.text
            assert response.json()["code"] == "operation_conflict"


def test_dry_run_and_invalid_plan_leave_no_receipt(tmp_path):
    service = CanvasService(tmp_path / "data")
    body = payload(service)
    assert apply_plan(service, {**body, "dryRun": True})["dryRun"]
    assert receipts(service) == []
    with pytest.raises(ValueError):
        apply_plan(service, {**body, "plan": {"nodes": [{"invalid": True}]}})
    assert receipts(service) == []
    assert apply_plan(service, body)["ok"]


@pytest.mark.parametrize("phase", ["after_write", "save_graph", "readback"])
def test_interrupted_canvas_retains_pending_and_never_duplicates(tmp_path, monkeypatch, phase):
    service = CanvasService(tmp_path / "data")
    body = payload(service)
    before = service.view("draft", "draft")["graph"]

    def fail(*args, **kwargs):
        raise RuntimeError("injected interruption")

    kwargs = {}
    if phase == "after_write":
        kwargs["after_write"] = fail
    elif phase == "save_graph":
        monkeypatch.setattr(service, "save_graph", fail)
    else:
        monkeypatch.setattr("backend.canvas.operation_readback.verify_plan", fail)
    with pytest.raises(RuntimeError, match="injected"):
        apply_plan(service, body, **kwargs)
    after = service.view("draft", "draft")["graph"]
    assert (after == before) == (phase != "readback")
    assert [row[0] for row in receipts(service)] == ["pending"]
    with pytest.raises(NextStep) as error:
        apply_plan(service, body)
    assert error.value.code == "operation_incomplete"
    assert service.view("draft", "draft")["graph"] == after


def proposal_body(client, key="proposal-1", plan=None):
    context = client.get(BASE + "/context", params=SCOPE).json()
    return {**SCOPE, "operationId": key, "parentRevision": context["acceptedHead"],
            "expectedGraphDigest": context["graphDigest"], "subject": "Draft only",
            "plan": plan or {"nodes": [{"ref": "task", "kind": "node", "name": "Task"}]}}


def test_proposal_replay_after_native_acceptance_and_conflict(tmp_path):
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        body = proposal_body(client)
        before = client.get("/api/view", params=SCOPE).json()
        first = client.post(BASE, headers=AGENT, json=body)
        assert first.status_code == 200, first.text
        item = first.json()
        assert client.get("/api/view", params=SCOPE).json()["digest"] == before["digest"]
        accepted = client.post(BASE + "/" + item["id"] + "/accept", headers=HEADERS,
            json={**SCOPE, "expectedAcceptedHead": None, "expectedGraphDigest": item["graphDigest"],
                  "adoptBaseGraphDigest": item["graphDigest"]})
        assert accepted.status_code == 200, accepted.text
        assert client.post(BASE, headers=AGENT, json=body).json() == item
        graph = client.get("/api/view", params=SCOPE).json()["graph"]
        assert item["refs"]["task"] in {n["id"] for n in graph["nodes"]}
        for candidate, headers in [({**body, "subject": "Changed"}, AGENT), (body, HEADERS)]:
            response = client.post(BASE, headers=headers, json=candidate)
            assert response.status_code == 409, response.text
            assert response.json()["code"] == "operation_conflict"
        change = proposal_body(client, "change-1", {"updateNodes": [{"id": item["refs"]["task"], "fields": {"name": "Renamed"}}]})
        revised = client.post(BASE, headers=AGENT, json=change)
        assert revised.status_code == 200, revised.text
        assert client.post(BASE, headers=AGENT, json=change).json() == revised.json()


def test_proposal_receipt_failure_rolls_back_native_record(tmp_path, monkeypatch):
    from backend.canvas.operation_receipts import Receipt
    with TestClient(create_app(tmp_path / "data"), base_url=ORIGIN) as client:
        body = proposal_body(client)
        def fail(*args):
            raise ValueError("injected receipt failure")
        with monkeypatch.context() as patch:
            patch.setattr(Receipt, "complete", fail)
            response = client.post(BASE, headers=AGENT, json=body)
            assert response.status_code == 409
        assert client.get(BASE, params=SCOPE).json()["items"] == []
        assert receipts(client.app.state.service) == []
        assert client.post(BASE, headers=AGENT, json=body).status_code == 200


def test_receipt_scope_is_project_workspace_and_operation(tmp_path):
    from backend.canvas.operation_receipts import Receipt
    service = CanvasService(tmp_path / "data")
    db = service.db_for("draft")
    body = payload(service)
    receipt = Receipt(body, "canvas-plan", {"kind": "human"})
    with db:
        receipt.begin(db)
        receipt.complete(db, {"ok": True})
    assert receipt.replay(db) == {"ok": True}
    for changed in [{**body, "project": "another"}, {**body, "workspace": "another"}]:
        assert Receipt(changed, "canvas-plan", {"kind": "human"}).replay(db) is None
    assert Receipt(body, "graph-proposal", {"kind": "human"}).replay(db) is None
