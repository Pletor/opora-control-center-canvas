"""Rozhraní Projektu: kontrola mapy architektury bez modelu (docs/architektura-pro-agenty.md §5), odvozené
cesty zákazníka (§6) a brána cesty (docs/brana-cesty.md): plán přehrání a odevzdání dokladu. Model se nevolá."""

import json

from fastapi import APIRouter, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool

from backend.canvas.canvas_service import ProjectNotFound
from backend.project.architecture.journey_plan import JourneyConflict, JourneyNotFound, journey_plan
from backend.project.architecture.journey_runs import (
    BODY_LIMIT,
    JourneyRunInvalid,
    project_journeys,
    record_journey_run,
)
from backend.project.architecture.map_check import map_check
from backend.project.architecture.work_status import architecture_graph


def _journey_errors(action):
    """404 neznámý projekt nebo cesta, 409 rozbitá či nejednoznačná cesta, 422 tvar dokladu."""
    try:
        return action()
    except (ProjectNotFound, JourneyNotFound) as error:
        raise HTTPException(404, str(error)) from error
    except JourneyRunInvalid as error:
        raise HTTPException(422, str(error)) from error
    except JourneyConflict as error:
        raise HTTPException(409, str(error)) from error


def create_project_map_check_router(service):
    router = APIRouter(prefix="/api/project-architecture", tags=["project-architecture"])

    @router.get("/map-check")
    def map_check_view(project: str = Query(min_length=1, max_length=64), locate: bool = False):
        # `locate=1` přidá nálezům `solverId` (místo řešení, §5.1); rozklad stránky podle něj páruje díry cest (§5.3).
        return map_check(service, project, locate=locate)

    @router.get("/journeys")
    def journeys_view(project: str = Query(min_length=1, max_length=64)):
        return project_journeys(service, project)

    @router.get("/journey-plan")
    def journey_plan_view(project: str = Query(min_length=1, max_length=64),
                          journey: str = Query(min_length=1, max_length=64),
                          application: str | None = Query(default=None, min_length=1, max_length=64)):
        return _journey_errors(lambda: journey_plan(architecture_graph(service, project), journey, application))

    @router.post("/journey-runs")
    async def journey_runs_create(request: Request, project: str = Query(min_length=1, max_length=64)):
        raw = await request.body()
        if len(raw) > BODY_LIMIT:
            raise HTTPException(422, "Doklad je delší než 64 KiB.")
        try:
            body = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise HTTPException(422, "Doklad není platný JSON.") from error
        # Zápis do SQLite pod zámkem projektu neběží ve smyčce událostí.
        return await run_in_threadpool(_journey_errors, lambda: record_journey_run(service, project, body))

    return router
