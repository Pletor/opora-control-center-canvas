"""Rozhraní Projektu: stav webu domén. Hosty určuje jen graf projektu, požadavek žádnou URL nenese."""

from fastapi import APIRouter, Query


def create_project_web_status_router(web_status):
    router = APIRouter(prefix="/api/project-architecture", tags=["project-architecture"])

    @router.get("/web-status")
    def web_status_view(
        project: str = Query(min_length=1, max_length=64),
        domain: str | None = Query(default=None, min_length=1, max_length=128),
        refresh: bool = False,
    ):
        return web_status.status(project, domain, refresh)

    return router
