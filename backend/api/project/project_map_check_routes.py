"""Rozhraní Projektu: kontrola mapy architektury bez modelu (docs/architektura-pro-agenty.md §5) i přes worktree, odvozené
cesty zákazníka (§6) a brána cesty (docs/brana-cesty.md): plán přehrání, odevzdání dokladu a krátkodobý stav
„cesta právě běží“ (§3a, jen v paměti procesu). Model se nevolá."""

import json

from fastapi import APIRouter, HTTPException, Query, Request, Response
from starlette.concurrency import run_in_threadpool

from backend.canvas.canvas_service import ProjectNotFound
from backend.project.architecture.journey_plan import JourneyConflict, JourneyNotFound, journey_plan
from backend.project.architecture.journey_running import (
    JourneyRunning,
    JourneyRunUnknown,
    start_journey_run,
    validate_progress,
)
from backend.project.architecture.journey_runs import (
    BODY_LIMIT,
    JourneyRunInvalid,
    project_journeys,
    record_journey_run,
)
from backend.project.architecture.map_check import map_check
from backend.project.architecture.map_check_worktrees import worktree_overlay
from backend.project.architecture.work_status import architecture_graph


def _journey_errors(action):
    """404 neznámý projekt nebo cesta, 409 rozbitá či nejednoznačná cesta, 422 tvar dokladu."""
    try:
        return action()
    except (ProjectNotFound, JourneyNotFound, JourneyRunUnknown) as error:
        raise HTTPException(404, str(error)) from error
    except JourneyRunInvalid as error:
        raise HTTPException(422, str(error)) from error
    except JourneyConflict as error:
        raise HTTPException(409, str(error)) from error


async def _json_body(request, what):
    raw = await request.body()
    if len(raw) > BODY_LIMIT:
        raise HTTPException(422, f"{what} je delší než 64 KiB.")
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HTTPException(422, f"{what} není platný JSON.") from error


def create_project_map_check_router(service, running=None):
    # Stav „cesta právě běží“ žije jen v paměti procesu (docs/brana-cesty.md §3a); jeden na router.
    running = running if running is not None else JourneyRunning()
    router = APIRouter(prefix="/api/project-architecture", tags=["project-architecture"])

    @router.get("/map-check")
    def map_check_view(project: str = Query(min_length=1, max_length=64), locate: bool = False):
        # `locate=1` přidá nálezům `solverId` (místo řešení, §5.1); rozklad stránky podle něj páruje díry cest (§5.3).
        return map_check(service, project, locate=locate)

    @router.get("/map-check/worktrees")
    def map_check_worktrees_view(project: str = Query(min_length=1, max_length=64)):
        # Díry mainu a co s nimi dělá každý aktivní worktree (docs/navrhy/2026-10-28-kontrola-mapy-a-worktree.md §3).
        return _journey_errors(lambda: worktree_overlay(service, project))

    @router.get("/journeys")
    def journeys_view(project: str = Query(min_length=1, max_length=64)):
        return project_journeys(service, project, running)

    @router.get("/journey-plan")
    def journey_plan_view(project: str = Query(min_length=1, max_length=64),
                          journey: str = Query(min_length=1, max_length=64),
                          application: str | None = Query(default=None, min_length=1, max_length=64)):
        return _journey_errors(lambda: journey_plan(architecture_graph(service, project), journey, application))

    @router.post("/journey-runs")
    async def journey_runs_create(request: Request, project: str = Query(min_length=1, max_length=64)):
        body = await _json_body(request, "Doklad")
        # Zápis do SQLite pod zámkem projektu neběží ve smyčce událostí.
        record = await run_in_threadpool(_journey_errors, lambda: record_journey_run(service, project, body))
        # Doklad je zapsaný: cesta už neběží (§3a).
        running.finish(project, record["applicationId"], record["journeyId"])
        return record

    @router.post("/journey-runs/start")
    async def journey_runs_start(request: Request):
        body = await _json_body(request, "Start běhu")
        # Start čte graf (ověří cestu stejně jako plán), proto mimo smyčku událostí.
        return await run_in_threadpool(_journey_errors, lambda: start_journey_run(service, running, body))

    @router.post("/journey-runs/{run_id}/progress", status_code=204)
    async def journey_runs_progress(run_id: str, request: Request):
        body = await _json_body(request, "Průběh běhu")
        _journey_errors(lambda: running.progress(run_id, validate_progress(body)))
        return Response(status_code=204)

    return router
