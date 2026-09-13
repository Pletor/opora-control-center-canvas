"""Rozhraní kroku 1: připojení repozitáře nebo složky, založení projektu a jeho nastavení."""

from fastapi import APIRouter


def create_project_setup_router(service):
    router = APIRouter(prefix="/api", tags=["project-setup"])

    @router.get("/project-settings")
    def project_settings(project: str):
        return service.project_hub.settings(project)

    @router.post("/project-settings")
    def save_project_settings(payload: dict):
        return service.project_hub.save_settings(payload)

    @router.post("/local-project")
    def local_project(payload: dict):
        return service.project_hub.local_project(payload)

    @router.post("/empty-project")
    def empty_project(payload: dict):
        return service.project_hub.empty_project(payload)

    @router.post("/connect")
    def connect(payload: dict):
        return service.connect(payload.get("url"), payload.get("approved"))

    return router
