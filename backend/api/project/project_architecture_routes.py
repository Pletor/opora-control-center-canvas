"""Rozhraní architektury projektu (`docs/domeny-a-worktree.md` §9): čtení, přímý zápis, návrat k revizi a ruční migrace.

Architektura je jedna pro projekt a nad všemi worktree; logika je v `backend/canvas/project_architecture.py`.
"""

from fastapi import APIRouter, Request

from backend.canvas.migrate_architecture import migrate as migrate_architecture


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

    @router.post("/migrate")
    def migrate(payload: dict):
        # Ruční migrace (§5): nejdřív dryRun (výchozí), zápis jen s výslovným dryRun=false.
        if not isinstance(payload, dict) or not {"project"} <= set(payload) <= {"project", "dryRun"}:
            raise ValueError("Neplatný formát migrace (project, dryRun).")
        dry_run = payload.get("dryRun", True)
        if not isinstance(dry_run, bool):
            raise ValueError("dryRun musí být true nebo false.")  # noqa: TRY004
        return migrate_architecture(service, payload["project"], dry_run=dry_run)

    return router
