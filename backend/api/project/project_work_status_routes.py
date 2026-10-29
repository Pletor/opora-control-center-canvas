"""Rozhraní Projektu: stav práce na doménách a worktree (docs/domeny-a-worktree.md §7, §9)."""

from fastapi import APIRouter

from backend.project.architecture.work_status import work_status


def create_project_work_status_router(service):
    router = APIRouter(prefix="/api", tags=["project-work-status"])

    @router.get("/project-architecture/work-status")
    def project_work_status(project: str):
        return work_status(service, project)

    return router
