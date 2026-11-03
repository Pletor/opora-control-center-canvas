"""Routy mozku: přepínač brány (docs/brain-gate.md §1) a fronta úkolů (§6, H1b).

Logika je v `backend/brain_opora/determinism/gate_setting.py` a `task_queue.py`; srdce totéž dělá druhy brány
`task.create` / `task.cancel` (`kinds.py`) nad stejnými funkcemi. Přepínač i úkoly čte kdokoli;
přepínač mění jen člověk v UI (`require_human`, i při plné autonomii agentů). Úkoly píše a ruší člověk nebo
srdce téhož projektu (docs/brain-heart.md §5, `writer.py`); agent s plnou autonomií bez tokenu srdce ne.
Zeď projektu se zapnutou bránou člověka i srdce pouští, zápis úkolu tedy funguje i tam.
`/intake-setting` = povolení a denní strop Jevu vstupní brány (`intake_setting.py`, docs/navrhy/2026-10-30-vstupni-brana.md
§7): čte kdokoli, mění jen člověk (`require_human`).
`/brief-setting` = výslech srdce zapnutý a strop rešerše na požadavek (`brief_setting.py`,
docs/navrhy/2026-10-30-vyslech-srdce.md §8): čte kdokoli, mění člověk nebo agent při plné autonomii (`require_authority`).
`/tickets` = tickety práce s tělem, strojovou vrstvou a zpětnou vazbou (`ticket.py`, docs/navrhy/2026-11-03-novy-zaklad.md
§3.3) pro kartotéku v kanceláři: jen čtení, píše se jen druhy brány `ticket.*`.
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.api.brain_opora import models
from backend.api.brain_opora.writer import writer
from backend.brain_opora.determinism import (
    brief_setting,
    gate_setting,
    intake_setting,
    task_queue,
    ticket,
)
from backend.brain_opora.determinism.gate_payloads import GateError, parse_body
from backend.canvas.activity_log import require_authority, require_human

TASK_WRITER = "Úkoly fronty mozku píše a ruší jen člověk v UI nebo srdce projektu."


def _refused(error):
    return JSONResponse(error.body(), status_code=error.status)


def create_brain_router(service):
    router = APIRouter(prefix="/api/brain", tags=["brain"])

    @router.get("/gate-setting", responses=models.answers(200, models.GateSettingOut, 404, 422))
    def read_gate_setting(project: str = ""):
        try:
            return gate_setting.get(service, project)
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)

    @router.post("/gate-setting", openapi_extra=models.body(models.GateSettingIn),
                 responses=models.answers(200, models.GateSettingOut, 403, 404, 409, 422))
    async def save_gate_setting(request: Request):
        # Bránu zapíná a vypíná jen člověk; agent si ji nevypne ani s plnou autonomií.
        require_human(request.state.actor, "Bránu mozku zapíná a vypíná jen člověk v UI.")
        try:
            return gate_setting.write(service, parse_body(await request.body()))
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)

    @router.get("/intake-setting", responses=models.answers(200, models.IntakeSettingOut, 404, 422))
    def read_intake_setting(project: str = ""):
        try:
            return intake_setting.get(service, project)
        except GateError as error:
            return _refused(error)

    @router.post("/intake-setting", openapi_extra=models.body(models.IntakeSettingIn),
                 responses=models.answers(200, models.IntakeSettingOut, 403, 404, 409, 422))
    async def save_intake_setting(request: Request):
        # Jev posílá větu člověka mimo stroj: povolení a strop mění jen člověk (docs/navrhy/2026-10-30-vstupni-brana.md §7).
        require_human(request.state.actor, "Jev vstupní brány zapíná a jeho strop mění jen člověk v UI.")
        try:
            return intake_setting.write(service, parse_body(await request.body()))
        except GateError as error:
            return _refused(error)

    @router.get("/brief-setting", responses=models.answers(200, models.BriefSettingOut, 404, 422))
    def read_brief_setting(project: str = ""):
        try:
            return brief_setting.get(service, project)
        except GateError as error:
            return _refused(error)

    @router.post("/brief-setting", openapi_extra=models.body(models.BriefSettingIn),
                 responses=models.answers(200, models.BriefSettingOut, 403, 404, 409, 422))
    async def save_brief_setting(request: Request):
        require_authority(request.state.actor,
                          "Výslech srdce a strop rešerše mění jen člověk v UI, nebo agent při plné autonomii.")
        try:
            return brief_setting.write(service, parse_body(await request.body()))
        except GateError as error:
            return _refused(error)

    @router.get("/tasks", responses=models.answers(200, models.TasksOut, 404, 422))
    def list_tasks(project: str = "", workspace: str = "", status: str = ""):
        try:
            return task_queue.list_tasks(service, project, workspace, status)
        except GateError as error:
            return _refused(error)

    @router.post("/tasks", status_code=201, openapi_extra=models.body(models.TaskIn),
                 responses=models.answers(201, models.Task, 403, 404, 413, 422))
    async def create_task(request: Request):
        try:
            payload = parse_body(await request.body())
            project = payload.get("project") if isinstance(payload, dict) else ""
            by = writer(request, project if isinstance(project, str) else "", TASK_WRITER)
            return await run_in_threadpool(task_queue.create, service, payload, by)
        except GateError as error:
            return _refused(error)

    @router.post("/tasks/{task_id}/cancel", responses=models.answers(200, models.Task, 403, 404, 409))
    def cancel_task(task_id: str, request: Request, project: str = ""):
        by = writer(request, project, TASK_WRITER)
        try:
            return task_queue.cancel(service, project, task_id, by=by)
        except GateError as error:
            return _refused(error)

    @router.get("/tickets", responses=models.answers(200, models.WorkTicketsOut, 404, 422))
    def list_tickets(project: str = "", workspace: str = "", status: str = ""):
        try:
            return ticket.list_tickets(service, project, workspace, status)
        except GateError as error:
            return _refused(error)

    @router.get("/tickets/{ticket_id}", responses=models.answers(200, models.WorkTicket, 404))
    def read_ticket(ticket_id: str, project: str = ""):
        try:
            return ticket.get(service, project, ticket_id)
        except GateError as error:
            return _refused(error)

    return router
