"""Routy vstupní brány požadavků (docs/navrhy/2026-10-30-vstupni-brana.md §6,
docs/navrhy/2026-10-30-metriky-a-spoustece.md §5).

- `GET /api/intake?project=&workspace=`: pohled „Požadavky a plán“: oblasti plátna s aktivním milníkem (kritéria
  hotovo/nehotovo, postup v %), návrhy milníků, otevřené a odložené požadavky (s podmínkou), požadavky bez oblasti,
  posledních 50 vstupů a počty `pending` / `duplicates`. Jen čtení; vstupy zapisuje server sám (zpráva srdce,
  lístek brány, fragment Schránky).
- `POST /api/intake/milestone {project, workspace, milestoneId, action: activate|reject}`: jen člověk v UI, nebo agent
  (srdce) v projektu s plnou autonomií (`require_authority`, docs/plna-autonomie-agenta.md §2); rozhodne o návrhu milníku srdce. Aktivace nahradí aktivní milník oblasti (`superseded`).
- `POST /api/intake/brief/answer {project, workspace, requirement, question, answer | accept: true}`: odpověď na
  otázku výslechu (docs/navrhy/2026-10-30-vyslech-srdce.md §7, řez 3); `accept` vezme doporučení srdce. Jen člověk,
  nebo agent při plné autonomii. Srdce se probudí jednou na odpověď (`brief.human_wakes`).
- `POST /api/intake/brief/start {project, workspace, requirement}`: „Vyslechni mě k tomu“, založí spis `draft`
  a probudí srdce jednou. Stejné oprávnění.
Logika je v `backend/brain_opora/determinism/intake.py`, `milestones.py` a `brief.py`.
"""
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.api.brain_opora import models
from backend.brain_opora.determinism import brief, intake, milestones
from backend.brain_opora.determinism.gate_payloads import GateError, parse_body
from backend.canvas.activity_log import HumanRequired, require_authority, require_human
from backend.canvas.authority import project_autonomy


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
        # Milník mění, co se smí stavět dál: aktivuje ho nebo zamítá jen člověk, nebo agent při plné autonomii.
        require_authority(request.state.actor,
                          "Milník oblasti aktivuje nebo zamítá jen člověk v UI, nebo agent při plné autonomii.")
        try:
            payload = parse_body(await request.body())
            if request.state.actor != "human":
                # Token srdce má v projektu vždy oprávnění; o milníku ale smí rozhodnout jen při zapnuté autonomii.
                project = payload.get("project") if isinstance(payload, dict) else None
                if not isinstance(project, str) or not project_autonomy(service, project)["full"]:
                    raise HumanRequired(request.state.actor, "Rozhodne člověk ve Velínu.")
            return await run_in_threadpool(milestones.decide, service, payload)
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)

    async def _human_channel(request, message):
        """Tělo kanálu člověka do výslechu: člověk vždy, agent (i token srdce) jen při plné autonomii projektu."""
        require_authority(request.state.actor, message)
        payload = parse_body(await request.body())
        if request.state.actor != "human":
            project = payload.get("project") if isinstance(payload, dict) else None
            if not isinstance(project, str) or not project_autonomy(service, project)["full"]:
                raise HumanRequired(request.state.actor, "Odpoví člověk ve Velínu.")
        return payload

    @router.post("/brief/answer", openapi_extra=models.body(models.BriefAnswerIn),
                 responses=models.answers(200, models.BriefAnswerOut, 403, 404, 409, 422))
    async def answer_brief(request: Request):
        # Otázky výslechu jsou kanál člověka do srdce: odpovídá jen člověk, i při plné autonomii (jinak by si srdce
        # odpovídalo samo; po třech kolech rozhodne samo a nejasnosti zapíše jako předpoklady, kontrakt §3.4).
        require_human(request.state.actor, "Na otázku výslechu odpovídá jen člověk ve Velínu.")
        try:
            payload = parse_body(await request.body())
            return await run_in_threadpool(brief.answer, service, payload, _now())
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)

    @router.post("/brief/start", status_code=201, openapi_extra=models.body(models.BriefStartIn),
                 responses=models.answers(201, models.BriefStartOut, 403, 404, 409, 422))
    async def start_brief(request: Request):
        # „Vyslechni mě k tomu“: člověk ve Velínu žádá výslech k požadavku; srdce se probudí jednou.
        try:
            payload = await _human_channel(
                request, "Výslech k požadavku spouští člověk v UI, nebo agent při plné autonomii.")
            return await run_in_threadpool(brief.start, service, payload, _now())
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)

    return router


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
