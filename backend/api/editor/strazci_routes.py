"""Rozhraní strážců (`docs/strazci.md` §5): stav strážců projektu, jejich nálezy a trend. Jen čtení."""
import time

from fastapi import APIRouter, HTTPException, Query

from backend.canvas.strazci.findings import at_of
from backend.canvas.strazci.guard_trend import METRICS, RETENTION_DAYS
from database.repositories.guard_findings import GuardFindings
from database.repositories.guard_trend import GuardTrend


def create_strazci_router(service, guardian, *, clock=time.time):
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

    @router.get("/trend")
    def trend_view(project: str = Query(min_length=1, max_length=64),
                   metric: str | None = Query(default=None, min_length=1, max_length=64),
                   days: int = Query(default=14, ge=1, le=RETENTION_DAYS)):
        known(project)
        if metric is not None and metric not in METRICS:
            raise HTTPException(422, f"Neznámé číslo trendu; známá: {', '.join(METRICS)}.")
        with service.reading(project):
            series = GuardTrend(service.db_for(project), project).series(at_of(clock() - days * 86400), metric)
        return {"metrics": list(METRICS) if metric is None else [metric], "days": days, "series": series}

    return router
