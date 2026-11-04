import json
import sqlite3
import threading
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from backend.api.flow.flow_routes import create_flow_router
from backend.app.factory import create_app
from backend.brain_opora.determinism import gate, tokens
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.activity_log import HumanRequired
from backend.canvas.test_canvas_plan import HEADERS, ORIGIN
from database.schema.opora_event_schema import SCHEMA as EVENT_SCHEMA
from database.schema.opora_event_schema import ensure_process_columns
from backend.flow.page_intents import page_digest
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


# Přijatý graf projektu `p` (projekt bez Gitu čte prostor `draft`): stránka kontakt a jedna aplikace.
PAGES = {"nodes": [{"id": "kontakt", "site": {"kind": "page", "path": "/kontakt", "goal": "Spojit se"}},
                   {"id": "o-nas", "site": {"kind": "page", "path": "/o-nas"}},
                   {"id": "app", "site": {"kind": "application"}}], "edges": []}


def client(graph=PAGES):
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(REGISTRY_SCHEMA)
    ensure_flow_owner_ref(db)
    db.execute("INSERT INTO projects(id,name) VALUES('p','P')")
    app = FastAPI()

    @app.middleware("http")
    async def actor(request: Request, call_next):  # doklad UI hraje testovací hlavička
        request.state.actor = request.headers.get("x-test-actor", "agent")
        request.state.heart_project = request.headers.get("x-test-heart", "")  # zeď po ověření tokenu srdce
        return await call_next(request)

    @app.exception_handler(HumanRequired)
    async def human_required(request, exc):
        return JSONResponse({"error": str(exc), "humanRequired": True}, status_code=403)

    project = sqlite3.connect(":memory:", check_same_thread=False)
    project.executescript(EVENT_SCHEMA)
    ensure_process_columns(project)
    lock = threading.RLock()
    hub = SimpleNamespace(settings=lambda pid: {"project": {"sourceKind": "local"}})
    service = SimpleNamespace(db=db, registry_lock=threading.RLock(), db_for=lambda pid: project,
                              lock_for=lambda pid: lock, project_hub=hub,
                              view=lambda pid, workspace: {"graph": graph})
    app.include_router(create_flow_router(service))
    client = TestClient(app)
    client.project_db = project
    return client, db


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
    decision = f"/api/flow/node-runs/{approval['id']}/decision"
    human = {"x-test-actor": "human"}
    agent = c.post(decision, json={"decision": "approved", "actor": "human"})  # autor z těla nic neodemkne
    assert agent.status_code == 403 and agent.json()["humanRequired"] is True
    done = c.post(decision, json={"decision": "approved"}, headers=human).json()
    assert done["status"] == "succeeded"
    again = c.post(decision, json={"decision": "rejected"}, headers=human)
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
                                      "schema": None, "required": False, "label": "model"}
    assert agent[("tool", "in")]["cardinality"] == "many"
    assert [p["name"] for p in types["approval.human"]["ports"] if p["direction"] == "out"] == [
        "approved", "rejected", "timeout"]


def test_node_types_library_flow_carry_layer_and_guidance():
    c, _ = client()
    types = {t["type"]: t for t in c.get("/api/flow/node-types", params={"kind": "library_flow"}).json()["node_types"]}
    assert {types[n]["layer"] for n in ("fe.click", "be.endpoint", "db.read", "infra.api", "ai.agent", "flow.if")} == {
        "fe", "be", "db", "infra", "ai", "neutral"}
    endpoint = types["be.endpoint"]
    assert endpoint["use"].startswith("Použij") and endpoint["avoid"].startswith("Nepoužívej")
    assert endpoint["intents"] == ["input", "call-service"] and set(endpoint["params"]) >= {"method", "path"}
    assert not any(name.startswith("action.") for name in types)
    assert (endpoint["accepts"], endpoint["emits"]) == (["json", "event"], "json")
    assert (types["db.read"]["accepts"], types["db.read"]["emits"]) == ([], "table")
    assert (types["flow.if"]["accepts"], types["flow.if"]["emits"]) == ([], None)


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
    assert json.loads(log[0]["payload"])["pageDigest"] == page_digest(PAGES["nodes"][0]["site"])


def test_canvas_log_takes_human_heart_and_gate_session_of_the_project(monkeypatch):
    c, db = client()
    entry = {"project": "p", "canvas": 2, "kind": "intent.failed", "payload": {"pageId": "kontakt", "nodeId": "ok"}}
    refused = c.post("/api/flow/log", json=entry)  # agent bez tokenu
    assert refused.status_code == 401 and refused.json()["code"] == "gate_token_invalid"
    assert c.post("/api/flow/log", json=entry, headers={"x-test-heart": "jiny"}).status_code == 401
    human = c.post("/api/flow/log", json=entry, headers={"x-test-actor": "human"})
    assert human.status_code == 200 and human.json()["canvas"] == 2
    assert c.post("/api/flow/log", json={**entry, "kind": "page.opened"}, headers={"x-test-heart": "p"}).status_code == 200

    def authenticate(service, token, project, roles):
        if token != "tok-worker" or project != "p":
            raise GateError(403, "gate_scope", "Cizí projekt.", "")
        return {"role": "worker", "project_id": "p"}

    monkeypatch.setattr(gate, "authenticate", authenticate)
    assert c.post("/api/flow/log", json=entry, headers={"X-Opora-Gate-Token": "tok-worker"}).status_code == 200
    assert c.post("/api/flow/log", json={**entry, "project": "q"},
                  headers={"X-Opora-Gate-Token": "tok-worker"}).status_code == 403
    for bad in ({"canvas": 1}, {"kind": "Spatne"}, {"payload": {"x": "y" * 5000}}):
        assert c.post("/api/flow/log", json={**entry, **bad}, headers={"x-test-actor": "human"}).status_code == 422
    assert c.post("/api/flow/log", json={**entry, "project": "nikdo"},
                  headers={"x-test-actor": "human"}).status_code == 404

    log = db.execute("SELECT type, canvas, payload, run_id FROM flow_log_events ORDER BY seq").fetchall()
    assert [(row["type"], row["canvas"], json.loads(row["payload"])["author"]) for row in log] == [
        ("intent.failed", 2, "human"), ("page.opened", 2, "heart"), ("intent.failed", 2, "worker")]
    assert all(row["run_id"] is None for row in log)
    events = c.project_db.execute("SELECT kind, workspace_id, data FROM opora_events ORDER BY id").fetchall()
    assert [(kind, space) for kind, space, _ in events] == [("canvas.failed", "draft")] * 2  # jen chyby budí srdce
    assert json.loads(events[0][2])["payload"] == entry["payload"]


def test_page_intents_list_every_page_with_its_state_and_graph_check():
    graph = {"nodes": [dict(node) for node in PAGES["nodes"]], "edges": []}
    c, _ = client(graph)
    wid = c.post("/api/flow/workflows", json={"kind": "page_intent", "name": "Kontakt", "project_id": "p",
                                              "owner_ref": "opora:page:kontakt"}).json()["id"]
    v1 = c.post(f"/api/flow/workflows/{wid}/versions", json={"graph": INTENT}).json()["id"]
    c.post(f"/api/flow/versions/{v1}/candidate", json={})
    states = c.get("/api/flow/page-intents", params={"project": "p"}).json()["pages"]
    assert states == [{"pageId": "kontakt", "state": "pending", "workflowId": wid, "candidateN": 1, "doneCount": 1},
                      {"pageId": "o-nas", "state": "none", "doneCount": 0}]
    c.post(f"/api/flow/versions/{v1}/approve", headers={"x-test-actor": "human"})
    assert c.get("/api/flow/page-intents", params={"project": "p"}).json()["pages"][0]["state"] == "approved"
    graph["nodes"][0] = {"id": "kontakt", "site": {"kind": "page", "path": "/kontakt", "goal": "Jiný cíl"}}
    assert c.get("/api/flow/page-intents", params={"project": "p"}).json()["pages"][0]["state"] == "stale"
    assert c.get("/api/flow/page-intents").status_code == 422

    assert c.post("/api/flow/graph-check", json={"kind": "page_intent", "graph": INTENT}).json() == {"ok": True, "errors": []}
    bad = c.post("/api/flow/graph-check", json={"kind": "page_intent", "graph": GRAPH}).json()
    assert bad["ok"] is False and any("intent.done" in error for error in bad["errors"])


def test_gate_wall_guards_flow_writes_with_project_id_or_by_id(tmp_path):
    """Brána zapnutá: agent bez tokenu nezaloží workflow s `project_id` ani nemění workflow podle ID; srdce smí."""
    agent = {**HEADERS, "X-Opora-Actor": "agent; name=dev"}
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as c:
        pid = c.post("/api/empty-project", headers=HEADERS, json={"name": "Tok", "confirmed": True}).json()["id"]
        assert c.post("/api/brain/gate-setting", headers=HEADERS, json={"project": pid, "enabled": True}).status_code == 200
        body = {"kind": "heart", "name": "Tok", "project_id": pid}
        refused = c.post("/api/flow/workflows", headers=agent, json=body)
        assert refused.status_code == 403 and refused.json()["code"] == "gate_required"
        wid = c.post("/api/flow/workflows", headers=HEADERS, json=body).json()["id"]
        draft = c.post(f"/api/flow/workflows/{wid}/versions", headers=agent, json={"graph": GRAPH})
        assert draft.status_code == 403 and draft.json()["code"] == "gate_required"
        assert c.post(f"/api/flow/workflows/{wid}/rollback", headers=agent, json={}).json()["code"] == "gate_required"
        _, heart = tokens.issue_heart(c.app.state.service, pid, "draft")
        made = c.post(f"/api/flow/workflows/{wid}/versions", headers={**agent, tokens.HEADER: heart}, json={"graph": GRAPH})
        assert made.status_code == 200, made.text
        vid = made.json()["id"]
        assert c.post(f"/api/flow/versions/{vid}/activate", headers=agent, json={}).json()["code"] == "gate_required"
        assert c.post(f"/api/flow/versions/{vid}/activate", headers={**agent, tokens.HEADER: heart}, json={}).status_code == 409


def test_node_ports_follow_params_of_dynamic_types():
    c, _ = client()
    url, kind = "/api/flow/node-ports", "library_flow"
    insert = c.post(url, json={"kind": kind, "type": "ai.vectorStore", "params": {"mode": "insert"}}).json()["ports"]
    assert {(p["name"], p["direction"]) for p in insert} == {("main", "in"), ("embedding", "in"), ("document", "in"),
                                                            ("main", "out")}
    tool = c.post(url, json={"kind": kind, "type": "ai.vectorStore", "params": {"mode": "retrieveAsTool"}}).json()
    assert [(p["name"], p["direction"], p["required"]) for p in tool["ports"]] == [
        ("embedding", "in", True), ("reranker", "in", False), ("tool", "out", False)]
    parser = c.post(url, json={"kind": kind, "type": "ai.agent", "params": {"hasOutputParser": True}}).json()["ports"]
    assert any(p["name"] == "outputParser" and p["label"] == "Výstupní parser" for p in parser)
    error = c.post(url, json={"kind": kind, "type": "infra.api", "params": {}, "onError": "errorOutput"}).json()
    assert [p["name"] for p in error["ports"] if p["direction"] == "out"] == ["main", "error"]
    assert c.post(url, json={"kind": kind, "type": "nope"}).status_code == 404


def test_simulate_route_replays_cases_reads_only_and_answers_422_in_czech(tmp_path):
    from backend.flow.test_simulate import BAD_CASE, OK_CASE, bmi_graph

    graph = bmi_graph([OK_CASE, BAD_CASE])
    with TestClient(create_app(tmp_path), base_url=ORIGIN) as c:
        done = c.post("/api/flow/simulate", headers=HEADERS, json={"graph": graph, "caseId": "ok"})
        assert done.status_code == 200
        body = done.json()
        assert body["ok"] and body["expect"] == {"ok": True, "diffs": []} and body["notify"] == "BMI 24.7 uloženo"
        assert body["trace"][3]["out"]["bmi"] == 24.7
        bad = c.post("/api/flow/simulate", headers=HEADERS, json={"graph": graph, "case": BAD_CASE}).json()
        assert bad["trace"][2]["branch"] == "false" and bad["notify"] == "Neplatná výška"
        for payload, text in (({"graph": graph}, "právě jedno"), ({"graph": graph, "caseId": "x"}, "nemá případ"),
                              ({"graph": {"nodes": 1}, "caseId": "x"}, "seznamy objektů")):
            refused = c.post("/api/flow/simulate", headers=HEADERS, json=payload)
            assert refused.status_code == 422 and text in refused.json()["detail"]
        assert c.get("/api/flow/workflows").json() == {"workflows": []}  # čtení: do registru nic nepřibylo
