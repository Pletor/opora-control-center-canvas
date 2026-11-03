import json
import sqlite3
import threading
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from backend.api.flow.flow_routes import create_flow_router
from backend.canvas.activity_log import HumanRequired
from database.schema.project_schema import REGISTRY_SCHEMA, ensure_flow_owner_ref

# Schválení s nulovým limitem: hned po spuštění je to prostoj (deadline vypršel), rozhodnutí ho uzavře.
GRAPH = {"nodes": [{"id": "t", "type": "trigger.manual"},
                   {"id": "a", "type": "approval.human", "params": {"timeout_seconds": 0}},
                   {"id": "e", "type": "debug.echo"}],
         "edges": [{"id": "1", "source_node": "t", "source_port": "main", "target_node": "a",
                    "target_port": "main", "kind": "main"},
                   {"id": "2", "source_node": "a", "source_port": "approved", "target_node": "e",
                    "target_port": "main", "kind": "main"}]}

INTENT = {"nodes": [{"id": "in", "type": "intent.entry", "params": {"from": "odkaz"}},
                    {"id": "ok", "type": "intent.done", "params": {"claim": "formulář odešel", "check": "email"}}],
          "edges": [{"id": "1", "source_node": "in", "source_port": "main", "target_node": "ok",
                     "target_port": "main", "kind": "main"}]}


def client():
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(REGISTRY_SCHEMA)
    ensure_flow_owner_ref(db)
    db.execute("INSERT INTO projects(id,name) VALUES('p','P')")
    app = FastAPI()

    @app.middleware("http")
    async def actor(request: Request, call_next):  # doklad UI hraje testovací hlavička
        request.state.actor = request.headers.get("x-test-actor", "agent")
        return await call_next(request)

    @app.exception_handler(HumanRequired)
    async def human_required(request, exc):
        return JSONResponse({"error": str(exc), "humanRequired": True}, status_code=403)

    app.include_router(create_flow_router(SimpleNamespace(db=db, registry_lock=threading.RLock())))
    return TestClient(app), db


def test_workflow_versions_run_decision_and_log():
    c, _ = client()
    wid = c.post("/api/flow/workflows", json={"kind": "heart", "name": "Tok"}).json()["id"]
    missing = c.post("/api/flow/workflows", json={"kind": "heart", "name": "X", "project_id": "nikdo"})
    assert missing.status_code == 404
    bad = {"nodes": [{"id": "x", "type": "nope"}], "edges": []}
    assert c.post(f"/api/flow/workflows/{wid}/versions", json={"graph": bad}).status_code == 422
    vid = c.post(f"/api/flow/workflows/{wid}/versions", json={"graph": GRAPH}).json()["id"]
    assert c.post(f"/api/flow/versions/{vid}/activate").status_code == 409
    assert c.post(f"/api/flow/versions/{vid}/candidate", json={"eval_run_id": "ev1"}).json()["status"] == "candidate"
    assert c.post(f"/api/flow/versions/{vid}/activate").json()["status"] == "active"
    assert c.post(f"/api/flow/workflows/{wid}/rollback").status_code == 409
    assert c.get("/api/flow/workflows").json()["workflows"][0]["active_version_id"] == vid
    assert [v["id"] for v in c.get(f"/api/flow/workflows/{wid}/versions").json()["versions"]] == [vid]

    run = c.post(f"/api/flow/versions/{vid}/runs", json={"payload": {"stránka": "/"}}).json()
    assert run["status"] == "waiting"
    assert c.get("/api/flow/stalls").json()["stalls"][0]["node_id"] == "a"
    approval = next(r for r in run["node_runs"] if r["node_id"] == "a")
    done = c.post(f"/api/flow/node-runs/{approval['id']}/decision", json={"decision": "approved"}).json()
    assert done["status"] == "succeeded"
    again = c.post(f"/api/flow/node-runs/{approval['id']}/decision", json={"decision": "rejected"})
    assert again.status_code == 409
    assert c.get(f"/api/flow/runs/{run['id']}").json()["status"] == "succeeded"
    assert [r["id"] for r in c.get("/api/flow/runs", params={"workflow": wid}).json()["runs"]] == [run["id"]]
    events = c.get(f"/api/flow/runs/{run['id']}/log").json()["events"]
    tail = c.get(f"/api/flow/runs/{run['id']}/log", params={"seq": events[-2]["seq"]}).json()["events"]
    assert tail == events[-1:]
    assert c.get("/api/flow/runs/nic").status_code == 404
    assert c.post(f"/api/flow/runs/{run['id']}/advance").json()["status"] == "succeeded"
    assert c.get("/api/flow/stalls").json()["stalls"] == []


def test_node_types_expose_ports_for_the_editor():
    c, _ = client()
    types = {t["type"]: t for t in c.get("/api/flow/node-types").json()["node_types"]}
    assert types["trigger.manual"]["trigger"] is True
    assert not any(name.startswith("intent.") for name in types)
    agent = {(p["name"], p["direction"]): p for p in types["agent.claude"]["ports"]}
    assert agent[("model", "in")] == {"name": "model", "direction": "in", "kind": "model", "cardinality": "one",
                                      "schema": None}
    assert agent[("tool", "in")]["cardinality"] == "many"
    assert [p["name"] for p in types["approval.human"]["ports"] if p["direction"] == "out"] == [
        "approved", "rejected", "timeout"]


def test_node_types_filter_page_intent_catalog():
    c, _ = client()
    types = {t["type"]: t for t in c.get("/api/flow/node-types", params={"kind": "page_intent"}).json()["node_types"]}
    assert set(types) == {f"intent.{n}" for n in ("entry", "view", "action", "reaction", "data", "done", "error")}
    assert set(types["intent.action"]["params"]) == {"do", "section", "text"}
    kinds = {(p["name"], p["direction"], p["kind"]) for p in types["intent.view"]["ports"]}
    assert kinds == {("main", "in", "main"), ("main", "out", "main"), ("data", "in", "data"), ("data", "out", "data")}
    assert c.get("/api/flow/node-types", params={"kind": "laser"}).status_code == 422


def test_page_intent_owner_approval_and_not_runnable():
    c, db = client()
    page = {"kind": "page_intent", "name": "Kontakt", "project_id": "p", "owner_ref": "opora:page:kontakt"}
    assert c.post("/api/flow/workflows", json={**page, "owner_ref": None}).status_code == 422
    wid = c.post("/api/flow/workflows", json=page).json()["id"]
    taken = c.post("/api/flow/workflows", json=page)
    assert taken.status_code == 409 and taken.json()["code"] == "owner_taken"
    c.post("/api/flow/workflows", json={"kind": "heart", "name": "Srdce"})
    found = c.get("/api/flow/workflows", params={"project": "p", "kind": "page_intent",
                                                 "owner_ref": "opora:page:kontakt"}).json()["workflows"]
    assert [w["id"] for w in found] == [wid]

    assert c.post(f"/api/flow/workflows/{wid}/versions", json={"graph": GRAPH}).status_code == 422
    v1 = c.post(f"/api/flow/workflows/{wid}/versions", json={"graph": INTENT}).json()["id"]
    c.post(f"/api/flow/versions/{v1}/candidate", json={})
    refused = c.post(f"/api/flow/versions/{v1}/activate")
    assert refused.status_code == 409 and refused.json()["code"] == "approval_required"
    assert c.post(f"/api/flow/versions/{v1}/approve").status_code == 403  # token srdce či dělníka
    human = {"x-test-actor": "human"}
    assert c.post(f"/api/flow/versions/{v1}/approve", headers=human).json()["status"] == "active"
    run = c.post(f"/api/flow/versions/{v1}/runs", json={})
    assert run.status_code == 409 and run.json()["code"] == "not_runnable"

    v2 = c.post(f"/api/flow/workflows/{wid}/versions", json={"graph": INTENT}).json()["id"]
    c.post(f"/api/flow/versions/{v2}/candidate", json={})
    assert c.post(f"/api/flow/versions/{v2}/reject", json={"reason": "chybí mapa"}).status_code == 403
    assert c.post(f"/api/flow/versions/{v2}/reject", json={"reason": ""}, headers=human).status_code == 422
    rejected = c.post(f"/api/flow/versions/{v2}/reject", json={"reason": "chybí mapa"}, headers=human).json()
    assert rejected["status"] == "retired"
    log = db.execute("SELECT type, payload, canvas FROM flow_log_events ORDER BY seq").fetchall()
    assert [(row["type"], row["canvas"]) for row in log] == [("version.approved", 2), ("version.rejected", 2)]
    assert json.loads(log[1]["payload"]) == {"workflow_id": wid, "version_id": v2, "n": 2, "author": "human",
                                             "reason": "chybí mapa"}
