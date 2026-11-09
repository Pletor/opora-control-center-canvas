"""Eval gate přes API: kandidát (člověk / srdce), eval v pozadí, aktivace 409 bez evalu, force jen člověk, návrat."""
import sqlite3
import json
import threading
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.api.brain import brain_registry_routes as routes
from backend.brain import evaluate, seed
from backend.brain.test_evaluate import FakeEval
from backend.brain_opora.determinism.gate_payloads import GateError
from database.schema.project_schema import REGISTRY_SCHEMA

HEART = "opora:brain:skill:heart"
HUMAN = {"X-Test-Actor": "human"}
SRDCE = {"X-Opora-Gate-Token": "srdce"}


@pytest.fixture
def api(tmp_path, monkeypatch):
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(REGISTRY_SCHEMA)
    seed.ensure(db, tmp_path, ponytail_cache=tmp_path / "chybi")

    def authenticate(_service, token, _project, roles):
        if token != "srdce" or roles != ("heart",):
            raise GateError(401, "gate_token_invalid", "Token brány chybí.", "")
        return {"role": "heart"}

    monkeypatch.setattr(routes.gate, "authenticate", authenticate)
    monkeypatch.setattr(evaluate, "claude_path", lambda: "claude")
    fake = FakeEval()
    monkeypatch.setattr(evaluate, "_run", fake)
    app = FastAPI()

    @app.middleware("http")
    async def actor(request: Request, call_next):  # doklad UI hraje testovací hlavička
        request.state.actor = request.headers.get("x-test-actor", "unknown")
        return await call_next(request)

    service = SimpleNamespace(db=db, root=tmp_path, registry_lock=threading.RLock())
    app.state.service = service
    app.include_router(routes.create_brain_registry_router(service, spawn=lambda target: target()))
    return TestClient(app)


def post(client, path, body=None, headers=None):
    return client.post(f"/api/brain-registry{path}", json=body or {}, headers=headers or {})


def candidate(client, text, headers=SRDCE):
    return post(client, f"/artifacts/{HEART}/candidates", {"files": {"skills/heart/SKILL.md": text},
                                                            "message": "kandidát"}, headers)


def test_candidate_needs_human_or_heart_and_refuses_evals(api):
    assert candidate(api, "x", headers={}).status_code == 401
    assert candidate(api, "x", headers={"X-Test-Actor": "agent"}).status_code == 401
    assert candidate(api, "Od člověka SKORE=0.6", headers=HUMAN).status_code == 201
    created = candidate(api, "Od srdce SKORE=0.6")
    assert created.status_code == 201 and created.json()["status"] == "candidate"
    frozen = post(api, f"/artifacts/{HEART}/candidates", {"files": {"evals/a/prompt.md": "x"}}, SRDCE)
    assert frozen.status_code == 422 and frozen.json()["code"] == "evals_frozen"


def test_activation_waits_for_a_passed_eval(api):
    vid = candidate(api, "Lepší SKORE=0.9").json()["id"]
    refused = post(api, f"/versions/{vid}/activate", headers=SRDCE)
    assert refused.status_code == 409 and refused.json()["code"] == "eval_required"
    run = post(api, f"/versions/{vid}/evaluate", headers=SRDCE)
    assert run.status_code == 202 and run.json()["status"] == "running"
    done = api.get(f"/api/brain-registry/eval-runs/{run.json()['id']}").json()
    assert done["status"] == "ok" and done["passed"] and done["score"] == 0.9
    activated = post(api, f"/versions/{vid}/activate", headers=SRDCE)
    assert activated.status_code == 200 and activated.json()["status"] == "active"
    assert api.get(f"/api/brain-registry/artifacts/{HEART}").json()["active"]["id"] == vid


def test_losing_candidate_stays_out_and_force_is_human_only(api):
    vid = candidate(api, "Horší SKORE=0.1").json()["id"]
    assert not api.get(f"/api/brain-registry/eval-runs/"
                       f"{post(api, f'/versions/{vid}/evaluate', headers=SRDCE).json()['id']}").json()["passed"]
    assert post(api, f"/versions/{vid}/activate", headers=SRDCE).json()["code"] == "eval_required"
    heart_force = post(api, f"/versions/{vid}/activate", {"force": True}, SRDCE)
    assert heart_force.status_code == 403 and heart_force.json()["code"] == "human_required"
    forced = post(api, f"/versions/{vid}/activate", {"force": True}, HUMAN)
    assert forced.status_code == 200 and forced.json()["status"] == "active"
    detail = api.get(f"/api/brain-registry/artifacts/{HEART}").json()
    runs = [link["target_ref"] for link in detail["versions"][0]["links"]]
    statuses = [api.get(f"/api/brain-registry/eval-runs/{rid}").json()["status"] for rid in runs]
    assert statuses == ["ok", "forced"]


def test_rollback_returns_to_the_previous_active_version_without_eval(api):
    seeded = api.get(f"/api/brain-registry/artifacts/{HEART}").json()["active"]["id"]
    assert post(api, f"/artifacts/{HEART}/rollback", headers=SRDCE).json()["code"] == "no_previous_version"
    vid = candidate(api, "Nová SKORE=0.7").json()["id"]
    post(api, f"/versions/{vid}/activate", {"force": True}, HUMAN)
    assert post(api, f"/artifacts/{HEART}/rollback").status_code == 401
    back = post(api, f"/artifacts/{HEART}/rollback", headers=SRDCE)
    assert back.status_code == 200 and back.json()["id"] == seeded and back.json()["status"] == "active"
    assert post(api, f"/artifacts/{HEART}/rollback", headers=SRDCE).status_code == 409  # dál už není kam


def test_evaluate_refuses_non_candidates(api):
    seeded = api.get(f"/api/brain-registry/artifacts/{HEART}").json()["active"]["id"]
    assert post(api, f"/versions/{seeded}/evaluate", headers=SRDCE).json()["code"] == "not_candidate"
    assert post(api, "/versions/nic/evaluate", headers=SRDCE).status_code == 404
    assert post(api, "/versions/nic/activate", headers=HUMAN).status_code == 404


def test_control_center_historical_equal_zero_or_partial_proof_cannot_activate(api):
    artifact="opora:brain:skill:opora-control-center"
    files={"skills/opora-control-center/SKILL.md":"Candidate routing"}
    vid=post(api,f"/artifacts/{artifact}/candidates",{"files":files},SRDCE).json()["id"]
    # Reproduce a persisted pre-upgrade evaluation behind the actual activation route.
    service=api.app.state.service
    run=evaluate.start(service.db,vid)
    for proof in (None,"malformed",{"schemaVersion":1,"passed":True,"cases":[]},
                  {"schemaVersion":1,"passed":True,"cases":[{"passed":True,"capabilities":[{"capability":[],"passed":True}]}]},
                  {"schemaVersion":1,"passed":True,"cases":[{"passed":True,"capabilities":[{"capability":"research_scope","passed":True}]}]}):
        report={"candidate":{}} if proof is None else {"candidate":{"operational":proof}}
        with service.db:
            service.db.execute("UPDATE brain_eval_runs SET status='ok',score=0,baseline_score=0,report_json=? WHERE id=?",
                               (json.dumps(report),run["id"]))
        assert evaluate.latest(service.db,vid)["passed"] is False
        response=post(api,f"/versions/{vid}/activate",headers=SRDCE)
        assert response.status_code==409 and response.json()["code"]=="eval_required"
    checks=[{"capability":key,"passed":True} for key in sorted(evaluate.operational_eval.CAPABILITIES)]
    report={"candidate":{"operational":{"schemaVersion":1,"passed":True,"cases":[{"passed":True,"capabilities":checks}]}}}
    with service.db:
        service.db.execute("UPDATE brain_eval_runs SET score=1,baseline_score=1,report_json=? WHERE id=?",(json.dumps(report),run["id"]))
    assert post(api,f"/versions/{vid}/activate",headers=SRDCE).status_code==200
