"""Rozhraní Projektu: pracovní větve projektu a aktualizace spravovaného mainu."""

from fastapi import APIRouter


def create_project_workspace_router(service):
    router = APIRouter(prefix="/api", tags=["project-workspaces"])

    @router.get("/project-workspaces")
    def project_workspaces(project: str):
        item = service.project_hub.settings(project)["project"]
        if item["sourceKind"] != "git":
            return {"workspaces": [{"id": "draft", "label": "Lokální pracovní návrh"}]}
        return {"workspaces": [{"id": "main", "label": "Schválená větev · pouze čtení"}] + [{"id": w["id"], "label": w["actor"] + " · " + w["branch"]} for w in service.workspaces(project)]}

    @router.post("/workspaces")
    def workspace(payload: dict):
        return service.create_workspace(
            payload.get("project"), payload.get("nodeId"), payload.get("actor")
        )

    @router.post("/sync")
    def sync(payload: dict):
        if payload.get("confirmed") is not True:
            raise ValueError("Potvrďte aktualizaci spravovaného mainu.")
        return service.sync(payload.get("project"))

    return router
