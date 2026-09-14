from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from backend.api.editor.process_routes import create_process_router
from backend.canvas.project_folder import ProjectFolder

HUMAN = {"kind": "human", "name": "Pletor"}
AGENT = {"kind": "agent", "name": "claude-code"}


def client_for(tmp_path):
    ProjectFolder(tmp_path, "p1").create("Projekt", "empty")
    app = FastAPI()

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"error": str(exc)}, status_code=409)

    app.include_router(create_process_router(SimpleNamespace(root=tmp_path)))
    return TestClient(app)


def test_full_lifecycle_through_api(tmp_path):
    client = client_for(tmp_path)
    created = client.post("/api/processes", json={"project": "p1", "title": "Reranker", "nodeId": "n1", "steps": ["a", "b"], "inputs": {"worktree": "wt-a"}, "by": HUMAN}).json()["process"]
    pid = created["id"]
    assert created["state"] == "draft" and created["projectId"] == "p1"

    listed = client.get("/api/processes", params={"project": "p1", "nodeId": "n1"}).json()["processes"]
    assert [p["id"] for p in listed] == [pid] and listed[0]["allowed"]["human"] == ["running"]

    run = client.post(f"/api/processes/{pid}/transition", json={"project": "p1", "revision": 1, "to": "running", "by": HUMAN}).json()["process"]
    assert run["state"] == "running" and run["revision"] == 2

    step_a, step_b = [s["id"] for s in run["steps"]]
    after_a = client.post(f"/api/processes/{pid}/reports", json={"project": "p1", "kind": "step_done", "stepId": step_a, "by": AGENT, "summary": "a hotovo", "processRevision": 2}).json()["process"]
    assert after_a["steps"][0]["state"] == "done" and after_a["revision"] == 3

    broken = client.post(f"/api/processes/{pid}/reports", json={"project": "p1", "kind": "step_failed", "stepId": step_b, "by": AGENT, "summary": "b spadlo", "error": "pytest failed", "processRevision": 3}).json()["process"]
    assert broken["state"] == "repair" and broken["revision"] == 4

    detail = client.get(f"/api/processes/{pid}", params={"project": "p1"}).json()
    assert len(detail["reports"]) == 2 and detail["reports"][-1]["kind"] == "step_failed"
    assert detail["allowed"]["agent"] == ["running"]

    fixed = client.post(f"/api/processes/{pid}/transition", json={"project": "p1", "revision": 4, "to": "running", "by": AGENT, "fix": "stabilní řazení"}).json()["process"]
    assert fixed["state"] == "running" and fixed["steps"][1]["state"] == "pending"

    done_b = client.post(f"/api/processes/{pid}/steps/{step_b}", json={"project": "p1", "revision": fixed["revision"], "state": "done", "evidence": {"summary": "14 passed", "at": "2026-09-14T10:00:00Z", "by": AGENT}}).json()["process"]
    finished = client.post(f"/api/processes/{pid}/transition", json={"project": "p1", "revision": done_b["revision"], "to": "done", "by": HUMAN}).json()["process"]
    assert finished["state"] == "done" and [h["to"] for h in finished["history"]] == ["draft", "running", "repair", "running", "done"]


def test_conflicts_and_forbidden_transitions_are_409(tmp_path):
    client = client_for(tmp_path)
    pid = client.post("/api/processes", json={"project": "p1", "title": "T", "by": HUMAN}).json()["process"]["id"]
    assert client.post(f"/api/processes/{pid}/transition", json={"project": "p1", "revision": 99, "to": "running", "by": HUMAN}).status_code == 409
    forbidden = client.post(f"/api/processes/{pid}/transition", json={"project": "p1", "revision": 1, "to": "done", "by": HUMAN})
    assert forbidden.status_code == 409 and "není povolen" in forbidden.json()["error"]
    assert client.get("/api/processes/prc-000000000000", params={"project": "p1"}).status_code == 409
    assert client.post("/api/processes", json={"project": "p1", "title": "T"}).status_code == 409
    assert client.get("/api/processes", params={"project": "../x"}).status_code == 409
