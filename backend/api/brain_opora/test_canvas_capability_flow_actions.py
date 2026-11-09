"""Real token/native workflow parity with isolated trigger/echo/approval executors."""
import pytest

from backend.api.brain_opora.test_canvas_capability_routes import setup, call, SCOPE
from backend.api.flow.test_flow_routes import GRAPH, INTENT
from backend.canvas.test_canvas_plan import HEADERS
from backend.flow import interpreter, review, workflows


@pytest.fixture(autouse=True)
def registered_fixture_project(setup):
    # create_app's draft canvas is not a registered workflow project.
    with setup[1].db:
        setup[1].db.execute("INSERT OR IGNORE INTO projects(id,name) VALUES('draft','Synthetic flow fixture')")


def fixture(service, kind="heart", project="draft", owner=None):
    workflow = workflows.create_workflow(service.db, kind, "Reviewed fixture", project, owner)
    version = workflows.create_draft(service.db, workflow["id"], INTENT if kind == "page_intent" else GRAPH)
    return workflow, version


def digest(service, operation, identifier):
    return review.observe(service.db, operation, identifier, "draft")["digest"]


def test_native_version_transitions_cas_replay_and_scope(setup):
    client, service, auth = setup
    workflow, first = fixture(service)
    payload = {"version_id": first["id"]}
    candidate = call(client, auth, "flow_routes.version_candidate", payload, "candidate")
    assert candidate.status_code == 200, candidate.text
    assert candidate.json()["result"]["status"] == "candidate"
    assert call(client, auth, "flow_routes.version_candidate", payload, "candidate").json() == candidate.json()
    payload["expectedReviewDigest"] = digest(service, "version_activate", first["id"])
    activate = call(client, auth, "flow_routes.version_activate", payload, "activate")
    assert activate.status_code == 200, activate.text
    second = workflows.create_draft(service.db, workflow["id"], GRAPH)
    workflows.set_candidate(service.db, second["id"])
    workflows.activate(service.db, second["id"])
    assert call(client, auth, "flow_routes.version_activate", payload, "activate").json() == activate.json()
    assert call(client, auth, "flow_routes.version_activate", payload, "stale").status_code == 409
    back = {"workflow_id": workflow["id"], "expectedReviewDigest": digest(service, "version_rollback", workflow["id"])}
    rolled = call(client, auth, "flow_routes.version_rollback", back, "rollback")
    assert rolled.status_code == 200 and rolled.json()["result"]["id"] == first["id"], rolled.text
    foreign = service.project_hub.empty_project({"name": "Foreign", "confirmed": True})["id"]
    _, hidden = fixture(service, project=foreign)
    assert call(client, auth, "flow_routes.version_candidate", {"version_id": hidden["id"]}, "foreign").status_code == 403
    assert call(client, auth, "flow_routes.review", {"operation": "version_activate", "identifier": hidden["id"]}).status_code == 403


def test_human_exact_version_review_and_stale_acceptance(setup):
    client, service, auth = setup
    workflow, version = fixture(service, "page_intent", owner="opora:page:fixture-page")
    workflows.set_candidate(service.db, version["id"])
    prepared = call(client, auth, "flow_routes.version_approve", {"version_id": version["id"]})
    assert prepared.status_code == 200 and not prepared.json()["applied"], prepared.text
    assert "flowReview=" + version["id"] in prepared.json()["url"]
    q = {**SCOPE, "operation": "version_approve", "identifier": version["id"]}
    observed = client.get("/api/flow/review", params=q, headers=auth)
    assert observed.status_code == 200 and observed.json()["selected"]["id"] == version["id"], observed.text
    assert client.get("/api/flow/review", params={**q, "workspace": "other"}, headers=auth).status_code == 403
    assert client.get("/api/flow/review", params={**q, "identifier": "missing"}, headers=auth).status_code == 404
    url = f"/api/flow/versions/{version['id']}/approve?expectedReviewDigest={observed.json()['digest']}"
    assert client.post(url, json={}, headers=auth).status_code == 403
    # Another human decision changes the same immutable selected version's lifecycle.
    workflows.reject(service.db, version["id"], "Fixture rejected", "human")
    assert client.post(url, json={}, headers=HEADERS).status_code == 409
    assert workflows.get_version(service.db, version["id"])["status"] == "retired"
    assert call(client, auth, "flow_routes.page_intent_list").status_code == 200


def test_run_start_replay_real_waiting_human_decision_and_scoped_stalls(setup):
    client, service, auth = setup
    _, version = fixture(service)
    body = {"version_id": version["id"], "payload": {"fixture": True}}
    started = call(client, auth, "flow_routes.run_manual", body, "manual-run")
    assert started.status_code == 200, started.text
    run = started.json()["result"]
    assert run["status"] == "waiting"
    assert call(client, auth, "flow_routes.run_manual", body, "manual-run").json() == started.json()
    assert len(interpreter.list_runs(service.db, version["workflow_id"])) == 1
    node = next(n for n in run["node_runs"] if n["node_id"] == "a")
    prep = call(client, auth, "flow_routes.approval_decision", {"node_run_id": node["id"], "decision": "approved"})
    assert prep.status_code == 200 and not prep.json()["applied"], prep.text
    url = f"/api/flow/node-runs/{node['id']}/decision?expectedReviewDigest={prep.json()['result']['digest']}"
    assert client.post(url, json={"decision": "approved"}, headers=auth).status_code == 403
    foreign = service.project_hub.empty_project({"name": "Foreign", "confirmed": True})["id"]
    _, other = fixture(service, project=foreign)
    hidden = interpreter.start_run(service.db, other["id"])
    stalls = call(client, auth, "flow_routes.stalls").json()["result"]["stalls"]
    assert any(s["run_id"] == run["id"] for s in stalls) and all(s["run_id"] != hidden["id"] for s in stalls)
    done = client.post(url, json={"decision": "approved"}, headers=HEADERS)
    assert done.status_code == 200 and done.json()["status"] == "succeeded", done.text
    assert call(client, auth, "flow_routes.run_advance", {"run_id": run["id"]}, "advance").json()["result"]["status"] == "succeeded"


def test_log_native_readback_replay_and_interrupted_run_never_duplicates(setup, monkeypatch):
    client, service, auth = setup
    body = {"canvas": 2, "kind": "fixture.failed", "payload": {"author": "fake", "project": "foreign"}}
    logged = call(client, auth, "flow_routes.canvas_log_create", body, "log")
    assert logged.status_code == 200, logged.text
    assert call(client, auth, "flow_routes.canvas_log_create", body, "log").json() == logged.json()
    _, version = fixture(service)
    original = interpreter.advance
    def interrupted(*args, **kwargs):
        raise RuntimeError("Fixture crash after durable run.created, before execution")
    monkeypatch.setattr(interpreter, "advance", interrupted)
    body = {"version_id": version["id"]}
    failed = call(client, auth, "flow_routes.run_manual", body, "interrupted")
    assert failed.status_code == 409 and failed.json()["code"] == "operation_incomplete", failed.text
    assert "interrupted" in failed.json()["hint"] and "reconcile" in failed.json()["hint"]
    before_retry = interpreter.list_runs(service.db, version["workflow_id"])
    assert len(before_retry) == 1 and before_retry[0]["status"] == "queued"
    monkeypatch.setattr(interpreter, "advance", original)
    retried = call(client, auth, "flow_routes.run_manual", body, "interrupted")
    assert retried.status_code == 409 and retried.json()["code"] == "operation_incomplete", retried.text
    runs = interpreter.list_runs(service.db, version["workflow_id"])
    assert len(runs) == 1 and runs[0]["status"] == "queued"
    assert runs[0]["id"] == before_retry[0]["id"]


def test_shared_human_library_prepares_exact_native_action_and_reject(setup):
    from backend.flow import library
    client, service, auth = setup
    folder = library.create_folder(service.db, "human", "flow-review-fixture", "Fixture")
    flow = library.create_flow(service.db, folder["id"], "flow", "Human flow")
    version = workflows.create_draft(service.db, flow["id"], {"nodes": [], "edges": []})
    data = {"version_id": version["id"]}
    prepared = call(client, auth, "flow_routes.version_candidate", data, "human-candidate")
    assert prepared.status_code == 200 and not prepared.json()["applied"], prepared.text
    assert workflows.get_version(service.db, version["id"])["status"] == "draft"
    stale_activation = {**data, "expectedReviewDigest": digest(service, "version_activate", version["id"])}
    response = client.post(f"/api/flow/versions/{version['id']}/candidate?expectedReviewDigest={prepared.json()['result']['digest']}", json={}, headers=HEADERS)
    assert response.status_code == 200, response.text
    stale = call(client, auth, "flow_routes.version_activate", stale_activation, "stale-human-review")
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "flow_review_stale", stale.text
    assert call(client, auth, "flow_routes.version_candidate", data, "human-candidate").json() == prepared.json()
    rejected = call(client, auth, "flow_routes.version_reject", data)
    assert rejected.status_code == 200 and not rejected.json()["applied"], rejected.text
    response = client.post(f"/api/flow/versions/{version['id']}/reject?expectedReviewDigest={rejected.json()['result']['digest']}", json={"reason": "Human fixture decision"}, headers=HEADERS)
    assert response.status_code == 200 and response.json()["status"] == "retired", response.text
    assert call(client, auth, "flow_routes.run_manual", data, "not-runnable").status_code == 409


def test_failed_log_missing_native_wake_is_not_reported_verified(setup, monkeypatch):
    from backend.flow import canvas_log
    client, service, auth = setup
    monkeypatch.setattr(canvas_log, "emit_event", lambda *a, **kw: None)
    data = {"canvas": 2, "kind": "fixture.failed", "payload": {}}
    failed = call(client, auth, "flow_routes.canvas_log_create", data, "missing-wake")
    assert failed.status_code == 409 and failed.json()["code"] == "operation_incomplete", failed.text
    retry = call(client, auth, "flow_routes.canvas_log_create", data, "missing-wake")
    assert retry.status_code == 409
    assert service.db.execute("SELECT COUNT(*) FROM flow_log_events WHERE type='fixture.failed'").fetchone()[0] == 1
