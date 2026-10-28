"""Routy mozku: přepínač brány (docs/brain-gate.md §1) a fronta úkolů (§6, H1b).

Logika je v `backend/brain_opora/determinism/gate_setting.py` a `task_queue.py`. Přepínač i úkoly čte kdokoli;
přepínač mění jen člověk v UI (`require_human`, i při plné autonomii agentů). Úkoly v H1b píše také jen člověk:
token srdce se tu zatím neuznává (přijde v H2 s vlastní kontrolou), aby si agent s plnou autonomií úkoly sám
nepsal. Zeď projektu se zapnutou bránou člověka pouští, zápis úkolu tedy funguje i tam.
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.brain_opora.determinism import gate_setting, task_queue
from backend.brain_opora.determinism.gate_payloads import GateError, parse_body
from backend.canvas.activity_log import require_human

TASK_WRITER = "Úkoly fronty mozku zatím píše a ruší jen člověk v UI (srdce přibude v H2)."


def _refused(error):
    return JSONResponse(error.body(), status_code=error.status)


def create_brain_router(service):
    router = APIRouter(prefix="/api/brain")

    @router.get("/gate-setting")
    def read_gate_setting(project: str = ""):
        try:
            return gate_setting.get(service, project)
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)

    @router.post("/gate-setting")
    async def save_gate_setting(request: Request):
        # Bránu zapíná a vypíná jen člověk; agent si ji nevypne ani s plnou autonomií.
        require_human(request.state.actor, "Bránu mozku zapíná a vypíná jen člověk v UI.")
        try:
            return gate_setting.write(service, parse_body(await request.body()))
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)

    @router.get("/tasks")
    def list_tasks(project: str = "", workspace: str = "", status: str = ""):
        try:
            return task_queue.list_tasks(service, project, workspace, status)
        except GateError as error:
            return _refused(error)

    @router.post("/tasks", status_code=201)
    async def create_task(request: Request):
        require_human(request.state.actor, TASK_WRITER)
        try:
            return await run_in_threadpool(task_queue.create, service, parse_body(await request.body()))
        except GateError as error:
            return _refused(error)

    @router.post("/tasks/{task_id}/cancel")
    def cancel_task(task_id: str, request: Request, project: str = ""):
        require_human(request.state.actor, TASK_WRITER)
        try:
            return task_queue.cancel(service, project, task_id)
        except GateError as error:
            return _refused(error)

    return router
