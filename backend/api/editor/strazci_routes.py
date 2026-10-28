"""Rozhraní strážců (`docs/strazci.md` §5): stav strážců projektu a jejich nálezy. Jen čtení."""

from fastapi import APIRouter, HTTPException, Query

from database.repositories.guard_findings import GuardFindings


def create_strazci_router(service, guardian):
    router = APIRouter(prefix="/api/strazci", tags=["strazci"])

    def known(project):
        if project not in service.project_ids():
            raise HTTPException(404, "Projekt neexistuje.")
        return project

    @router.get("")
    def guards_view(project: str = Query(min_length=1, max_length=64)):
        return guardian.status(known(project))

    @router.get("/findings")
    def findings_view(project: str = Query(min_length=1, max_length=64),
                      node: str | None = Query(default=None, min_length=1, max_length=200),
                      open: int = Query(default=1, ge=0, le=1)):
        known(project)
        with service.reading(project):
            items = GuardFindings(service.db_for(project), project).list(node=node, open_only=bool(open))
        return {"findings": items}

    return router
