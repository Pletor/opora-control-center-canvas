import json
import sqlite3
import threading
from contextlib import nullcontext
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.project.project_map_check_routes import create_project_map_check_router
from backend.canvas.canvas_service import ProjectNotFound
from database.schema.journey_run_schema import SCHEMA as JOURNEY_RUN_SCHEMA


def make_client(source_kind="git"):
    journeys = [{"id": "j1", "name": "Na b", "steps": [{"id": "s1", "page": "nav"}, {"id": "s2", "page": "b"}]},
                {"id": "j2", "name": "Domů", "steps": [{"id": "s1", "page": "nav"}, {"id": "s2", "page": "p", "shift": "Ví, kam dál."}]}]
    graph = {"nodes": [{"id": "app", "parentId": None, "kind": "sector",
                        "site": {"kind": "application", "journeys": journeys, "environments": [{"name": "Dev", "host": "localhost:3000"}]}},
                       {"id": "p", "parentId": "app", "kind": "node", "site": {"kind": "page", "path": "/"}},
                       {"id": "a", "parentId": "p", "kind": "node"}, {"id": "b", "parentId": "p", "kind": "node"}],
             "edges": [{"id": "e1", "source": "a", "target": "b"}]}
    seen = []

    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.executescript(JOURNEY_RUN_SCHEMA)

    def settings(project):
        if project == "nikdo":
            raise ProjectNotFound(project)
        return {"project": {"sourceKind": source_kind}}

    def view(project, wid):
        seen.append((project, wid))
        return {"graph": graph}

    workspaces = [{"id": "w1", "branch": "work/w1", "actor": "agent", "node_id": "app"}]
    service = SimpleNamespace(project_hub=SimpleNamespace(settings=settings), view=view, db_for=lambda project: db,
                              reading=lambda project: nullcontext(), lock_for=lambda project: threading.RLock(),
                              workspaces=lambda project: workspaces)
    app = FastAPI()
    app.include_router(create_project_map_check_router(service))
    return TestClient(app), seen


def test_map_check_reads_the_accepted_graph_and_returns_findings():
    client, seen = make_client()
    body = client.get("/api/project-architecture/map-check", params={"project": "p1"}).json()
    assert seen == [("p1", "main")]
    assert body["findings"] == [{"rule": "journey.broken", "journeyId": "j1",
                                 "message": "Cesta Na b: chybí stránka b v kroku s2."},
                                {"rule": "journey.unverified", "journeyId": "j2",
                                 "message": "Cesta Domů: chybí ověření (doklad přehrání cesty)."},
                                {"rule": "page.no-goal", "nodeId": "p", "message": "Stránka nemá cíl (goal)."},
                                {"rule": "edge.carries-unset", "edgeId": "e1",
                                 "message": "Vazba neříká, co nese (carries)."}]
    assert body["summary"]["page.no-goal"] == 1 and body["summary"]["edge.carries-unset"] == 1


def test_map_check_locate_adds_solver_ids():
    client, _ = make_client()
    body = client.get("/api/project-architecture/map-check", params={"project": "p1", "locate": "1"}).json()
    assert [(f["rule"], f["solverId"]) for f in body["findings"]] == [
        ("journey.broken", "app"), ("journey.unverified", "app"), ("page.no-goal", "p"), ("edge.carries-unset", "a")]


def test_map_check_uses_draft_without_git_and_requires_project():
    client, seen = make_client(source_kind="folder")
    assert client.get("/api/project-architecture/map-check", params={"project": "p1"}).status_code == 200
    assert seen == [("p1", "draft")]
    assert client.get("/api/project-architecture/map-check").status_code == 422


def test_map_check_worktrees_returns_the_overlay():
    client, seen = make_client()
    body = client.get("/api/project-architecture/map-check/worktrees", params={"project": "p1"}).json()
    assert seen == [("p1", "main"), ("p1", "w1")]
    assert [(f["rule"], f["solverId"]) for f in body["main"]] == [
        ("journey.broken", "app"), ("journey.unverified", "app"), ("page.no-goal", "p"), ("edge.carries-unset", "a")]
    assert body["worktrees"] == [{"workspaceId": "w1", "branch": "work/w1", "actor": "agent", "domainId": "app",
                                  "closed": [], "opened": []}]
    assert client.get("/api/project-architecture/map-check/worktrees", params={"project": "nikdo"}).status_code == 404
    assert client.get("/api/project-architecture/map-check/worktrees").status_code == 422


def test_journeys_returns_derived_steps_of_the_accepted_graph():
    client, seen = make_client()
    body = client.get("/api/project-architecture/journeys", params={"project": "p1"}).json()
    assert seen == [("p1", "main")]
    assert body == {"journeys": [
        {"applicationId": "app", "id": "j1", "name": "Na b", "broken": "chybí stránka b v kroku s2.",
         "steps": [{"id": "s1", "page": "nav", "path": "nav"}, {"id": "s2", "page": "b", "missing": True}], "running": None},
        {"applicationId": "app", "id": "j2", "name": "Domů", "line": "nav → /",
         "steps": [{"id": "s1", "page": "nav", "path": "nav"}, {"id": "s2", "page": "p", "path": "/", "shift": "Ví, kam dál."}],
         "segments": [{"from": "s1", "to": "s2", "line": "nav → /", "realized": True}], "running": None}]}
    assert client.get("/api/project-architecture/journeys").status_code == 422


def run_body(digest, ok=True):
    return {"schema": "opora.journey-run/1", "applicationId": "app", "journeyId": "j2", "planDigest": digest,
            "command": "uv run python tools/journey_run.py --journey j2", "at": "2026-10-27T21:40:00Z",
            "segments": [{"from": "s1", "to": "s2", "ok": ok, **({} if ok else {"reason": "URL /x, čekáno /"})}]}


def test_journey_plan_returns_the_plan_and_maps_errors():
    client, _ = make_client()
    plan = client.get("/api/project-architecture/journey-plan", params={"project": "p1", "journey": "j2"})
    assert plan.status_code == 200
    body = plan.json()
    assert body["baseUrl"] == "http://localhost:3000" and body["digest"].startswith("sha256:")
    assert body["segments"] == [{"from": "s1", "to": "s2", "open": "/", "scope": "nav", "do": "click", "expectPath": "/"}]
    assert client.get("/api/project-architecture/journey-plan",
                      params={"project": "p1", "journey": "j2", "application": "app"}).json() == body
    assert client.get("/api/project-architecture/journey-plan", params={"project": "p1", "journey": "zadna"}).status_code == 404
    assert client.get("/api/project-architecture/journey-plan", params={"project": "nikdo", "journey": "j2"}).status_code == 404
    broken = client.get("/api/project-architecture/journey-plan", params={"project": "p1", "journey": "j1"})
    assert broken.status_code == 409 and broken.json()["detail"] == "Cesta Na b: chybí stránka b v kroku s2."
    assert client.get("/api/project-architecture/journey-plan", params={"project": "p1"}).status_code == 422


def test_journey_run_is_recorded_and_shows_up_as_last_run():
    client, _ = make_client()
    digest = client.get("/api/project-architecture/journey-plan", params={"project": "p1", "journey": "j2"}).json()["digest"]
    url = "/api/project-architecture/journey-runs"
    saved = client.post(url, params={"project": "p1"}, json=run_body(digest, ok=False))
    assert saved.status_code == 200
    assert saved.json()["passed"] is False and saved.json()["verification"] == "agent-reported; not independently verified"
    journeys = client.get("/api/project-architecture/journeys", params={"project": "p1"}).json()["journeys"]
    assert "lastRun" not in journeys[0]
    assert journeys[1]["lastRun"] == {"at": "2026-10-27T21:40:00Z", "passed": False, "stale": False,
                                      "command": "uv run python tools/journey_run.py --journey j2", "failed": 1,
                                      "firstFailure": {"from": "s1", "to": "s2", "reason": "URL /x, čekáno /"}}
    findings = client.get("/api/project-architecture/map-check", params={"project": "p1"}).json()["findings"]
    assert [f["message"] for f in findings if f["rule"] == "journey.unverified"] == [
        "Cesta Domů: neprošel přechod s1 → s2 (URL /x, čekáno /)."]
    assert client.post(url, params={"project": "p1"}, json=run_body(digest)).status_code == 200
    findings = client.get("/api/project-architecture/map-check", params={"project": "p1"}).json()["findings"]
    assert not [f for f in findings if f["rule"] == "journey.unverified"]


def test_journey_run_errors_are_404_409_and_422():
    client, _ = make_client()
    url = "/api/project-architecture/journey-runs"
    digest = "sha256:" + "0" * 64
    assert client.post(url, params={"project": "p1"}, json={**run_body(digest), "journeyId": "zadna"}).status_code == 404
    assert client.post(url, params={"project": "nikdo"}, json=run_body(digest)).status_code == 404
    broken = {**run_body(digest), "journeyId": "j1"}
    assert client.post(url, params={"project": "p1"}, json=broken).status_code == 409
    assert client.post(url, params={"project": "p1"}, json={**run_body(digest), "planDigest": "x"}).status_code == 422
    assert client.post(url, params={"project": "p1"}, content=b"{nejson").status_code == 422
    huge = {**run_body(digest), "logUrl": "x" * (65 * 1024)}
    assert client.post(url, params={"project": "p1"}, content=json.dumps(huge).encode()).status_code == 422


def test_journey_running_start_progress_and_clear_after_record():
    client, _ = make_client()
    base = "/api/project-architecture/journey-runs"
    started = client.post(base + "/start", json={"project": "p1", "journeyId": "j2"})
    assert started.status_code == 200
    run_id = started.json()["runId"]
    assert started.json()["startedAt"].endswith("Z")
    journeys = client.get("/api/project-architecture/journeys", params={"project": "p1"}).json()["journeys"]
    assert journeys[0]["running"] is None
    assert journeys[1]["running"] == {"runId": run_id, "at": started.json()["startedAt"], "segment": None}
    progress = client.post(f"{base}/{run_id}/progress", json={"segment": {"from": "s1", "to": "s2"}})
    assert progress.status_code == 204 and progress.content == b""
    running = client.get("/api/project-architecture/journeys", params={"project": "p1"}).json()["journeys"][1]["running"]
    assert running["segment"] == {"from": "s1", "to": "s2"}
    digest = client.get("/api/project-architecture/journey-plan", params={"project": "p1", "journey": "j2"}).json()["digest"]
    assert client.post(base, params={"project": "p1"}, json=run_body(digest)).status_code == 200
    assert client.get("/api/project-architecture/journeys", params={"project": "p1"}).json()["journeys"][1]["running"] is None
    assert client.post(f"{base}/{run_id}/progress", json={"segment": {"from": "s1", "to": "s2"}}).status_code == 404


def test_journey_running_errors():
    client, _ = make_client()
    base = "/api/project-architecture/journey-runs"
    assert client.post(base + "/start", json={"project": "p1", "journeyId": "zadna"}).status_code == 404
    assert client.post(base + "/start", json={"project": "nikdo", "journeyId": "j2"}).status_code == 404
    assert client.post(base + "/start", json={"project": "p1", "journeyId": "j1"}).status_code == 409
    assert client.post(base + "/start", json={"project": "p1"}).status_code == 422
    assert client.post(base + "/start", content=b"{nejson").status_code == 422
    run_id = client.post(base + "/start", json={"project": "p1", "journeyId": "j2"}).json()["runId"]
    assert client.post(f"{base}/{run_id}/progress", json={"segment": "s1"}).status_code == 422
    assert client.post(f"{base}/neni/progress", json={"segment": {"from": "s1", "to": "s2"}}).status_code == 404


def test_intent_plan_and_run_follow_the_active_page_intent():
    from backend.project.architecture.test_intent_runs import intent_service, publish

    service, wid = intent_service()
    app = FastAPI()
    app.include_router(create_project_map_check_router(service))
    client = TestClient(app)
    query = {"project": "p", "page": "landing"}
    assert client.get("/api/project-architecture/intent-plan", params=query).status_code == 404
    publish(service, wid)
    plan = client.get("/api/project-architecture/intent-plan", params=query).json()
    assert plan["schema"] == "opora.intent-plan/1" and [n["nodeId"] for n in plan["nodes"]] == ["send", "ok"]
    run = {"pageId": "landing", "workflowVersionId": plan["workflowVersionId"], "digest": plan["digest"],
           "nodes": [{"nodeId": "send", "ok": True}, {"nodeId": "ok", "ok": False, "reason": "chybí text"}]}
    url = "/api/project-architecture/intent-runs?project=p"
    record = client.post(url, json=run).json()
    assert record["passed"] is False and record["stale"] is False
    assert client.post(url, json={**run, "digest": "x"}).status_code == 422
    assert client.post(url, json={**run, "pageId": "jina"}).status_code == 404
    assert service.db.execute("SELECT COUNT(*) FROM flow_log_events WHERE type='intent.failed'").fetchone()[0] == 1
