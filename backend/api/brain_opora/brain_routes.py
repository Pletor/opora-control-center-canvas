"""Routy mozku: přepínač brány (docs/brain-gate.md §1) a fronta úkolů (§6, H1b).

Logika je v `backend/brain_opora/determinism/gate_setting.py` a `task_queue.py`; srdce totéž dělá druhy brány
`task.create` / `task.cancel` (`kinds.py`) nad stejnými funkcemi. Přepínač i úkoly čte kdokoli;
přepínač mění jen člověk v UI (`require_human`, i při plné autonomii agentů). Úkoly píše a ruší člověk nebo
srdce téhož projektu (docs/brain-heart.md §5, `writer.py`); agent s plnou autonomií bez tokenu srdce ne.
Zeď projektu se zapnutou bránou člověka i srdce pouští, zápis úkolu tedy funguje i tam.
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.api.brain_opora import models
from backend.api.brain_opora.writer import writer
from backend.brain_opora.determinism import gate_setting, task_queue
from backend.brain_opora.determinism.gate_payloads import GateError, parse_body
from backend.canvas.activity_log import require_human

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

    return router
