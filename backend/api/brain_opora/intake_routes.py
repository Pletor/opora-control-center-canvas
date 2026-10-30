"""Routy vstupní brány požadavků (docs/navrhy/2026-10-30-vstupni-brana.md §6,
docs/navrhy/2026-10-30-metriky-a-spoustece.md §5).

- `GET /api/intake?project=&workspace=`: pohled „Požadavky a plán“: oblasti plátna s aktivním milníkem (kritéria
  hotovo/nehotovo, postup v %), návrhy milníků, otevřené a odložené požadavky (s podmínkou), požadavky bez oblasti,
  posledních 50 vstupů a počty `pending` / `duplicates`. Jen čtení; vstupy zapisuje server sám (zpráva srdce,
  lístek brány, fragment Schránky).
- `POST /api/intake/milestone {project, workspace, milestoneId, action: activate|reject}`: jen člověk v UI
  (`require_human`); rozhodne o návrhu milníku srdce. Aktivace nahradí aktivní milník oblasti (`superseded`).
Logika je v `backend/brain_opora/determinism/intake.py` a `milestones.py`.
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.api.brain_opora import models
from backend.brain_opora.determinism import intake, milestones
from backend.brain_opora.determinism.gate_payloads import GateError, parse_body
from backend.canvas.activity_log import require_human


def create_intake_router(service):
    router = APIRouter(prefix="/api/intake", tags=["intake"])

    @router.get("")
    def overview(project: str = "", workspace: str = ""):
        try:
            return intake.overview(service, project, workspace)
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)

    @router.post("/milestone", openapi_extra=models.body(models.MilestoneDecisionIn),
                 responses=models.answers(200, models.MilestoneDecisionOut, 403, 404, 409, 422))
    async def decide_milestone(request: Request):
        # Milník mění, co se smí stavět dál: aktivuje ho nebo zamítá jen člověk, srdce ho jen navrhne.
        require_human(request.state.actor, "Milník oblasti aktivuje nebo zamítá jen člověk v UI.")
        try:
            return await run_in_threadpool(milestones.decide, service, parse_body(await request.body()))
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)

    return router
