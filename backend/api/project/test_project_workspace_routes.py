"""Rozhraní worktree ↔ doména a skladiště (docs/domeny-a-worktree.md §9)."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from backend.api.project.project_workspace_routes import create_project_workspace_router
from backend.canvas.test_canvas_service import managed_fixture
from backend.canvas.test_project_architecture import domain
from backend.project.worktrees.test_workspace_archive import Hooks, Sessions
from backend.project.worktrees.test_workspace_domain import with_architecture
from backend.project.worktrees.workspace_archive import WorkspaceArchive


def test_create_rebind_archive_and_list(tmp_path):
    s, p = managed_fixture(tmp_path)
    pid = p["id"]
    with_architecture(s, pid, domain(), domain("dev", host="app.example.dev"))
    app = FastAPI()

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"error": str(exc)}, status_code=400)

    app.include_router(create_project_workspace_router(s, WorkspaceArchive(s, Sessions(), Hooks())))
    client = TestClient(app)
    try:
        refused = client.post("/api/workspaces", json={"project": pid, "nodeId": "project", "actor": "A"})
        assert refused.status_code == 400 and "doméně" in refused.json()["error"]
        wid = client.post("/api/workspaces", json={"project": pid, "nodeId": "app", "actor": "A"}).json()["id"]
        moved = client.patch(f"/api/workspaces/{wid}", json={"project": pid, "nodeId": "dev"})
        assert moved.status_code == 200 and moved.json()["node_id"] == "dev"
        body = {"project": pid, "reason": "Nevyšlo", "confirmed": True}
        assert client.post(f"/api/workspaces/{wid}/archive", json=body).json() == {
            "archived": wid, "branch": "work/" + wid}
        items = client.get("/api/workspaces/archive", params={"project": pid}).json()["items"]
        assert [(i["id"], i["nodeId"], i["reason"]) for i in items] == [(wid, "dev", "Nevyšlo")]
        assert client.patch(f"/api/workspaces/{wid}", json={"project": pid, "nodeId": "app"}).status_code == 400
    finally:
        s.close()
