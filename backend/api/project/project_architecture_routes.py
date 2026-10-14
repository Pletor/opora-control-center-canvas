"""Rozhraní architektury projektu (`docs/domeny-a-worktree.md` §9): čtení, přímý zápis a návrat k revizi.

Architektura je jedna pro projekt a nad všemi worktree; logika je v `backend/canvas/project_architecture.py`.
"""

from fastapi import APIRouter, Request


def create_project_architecture_router(service):
    router = APIRouter(prefix="/api/project-architecture", tags=["project-architecture"])

    @router.get("")
    def read(project: str):
        return service.architecture.public(project)

    @router.post("")
    def save(payload: dict, request: Request):
        # Aktér se bere z ověřeného požadavku; případné `actor` v těle je jen popisek klienta.
        return service.architecture.save(payload, actor=request.state.actor)

    @router.post("/restore")
    def restore(payload: dict, request: Request):
        return service.architecture.restore(payload, actor=request.state.actor)

    return router
