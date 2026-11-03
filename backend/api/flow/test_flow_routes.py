import sqlite3
import threading
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.flow.flow_routes import create_flow_router
from database.schema.project_schema import REGISTRY_SCHEMA

# Schválení s nulovým limitem: hned po spuštění je to prostoj (deadline vypršel), rozhodnutí ho uzavře.
GRAPH = {"nodes": [{"id": "t", "type": "trigger.manual"},
                   {"id": "a", "type": "approval.human", "params": {"timeout_seconds": 0}},
                   {"id": "e", "type": "debug.echo"}],
         "edges": [{"id": "1", "source_node": "t", "source_port": "main", "target_node": "a",
                    "target_port": "main", "kind": "main"},
                   {"id": "2", "source_node": "a", "source_port": "approved", "target_node": "e",
                    "target_port": "main", "kind": "main"}]}


def client():
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(REGISTRY_SCHEMA)
    app = FastAPI()
    app.include_router(create_flow_router(SimpleNamespace(db=db, registry_lock=threading.RLock())))
    return TestClient(app)


def test_workflow_versions_run_decision_and_log():
    c = client()
    wid = c.post("/api/flow/workflows", json={"kind": "page_intent", "name": "Záměr"}).json()["id"]
    missing = c.post("/api/flow/workflows", json={"kind": "page_intent", "name": "X", "project_id": "nikdo"})
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
