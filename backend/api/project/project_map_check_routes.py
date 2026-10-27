"""Rozhraní Projektu: kontrola mapy architektury bez modelu (docs/architektura-pro-agenty.md §5) a odvozené
cesty zákazníka (§6). Jen čtení."""

from fastapi import APIRouter, Query

from backend.project.architecture.journeys import project_journeys
from backend.project.architecture.map_check import map_check


def create_project_map_check_router(service):
    router = APIRouter(prefix="/api/project-architecture", tags=["project-architecture"])

    @router.get("/map-check")
    def map_check_view(project: str = Query(min_length=1, max_length=64)):
        return map_check(service, project)

    @router.get("/journeys")
    def journeys_view(project: str = Query(min_length=1, max_length=64)):
        return project_journeys(service, project)

    return router
