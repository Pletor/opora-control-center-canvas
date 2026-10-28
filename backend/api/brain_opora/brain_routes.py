"""Routy nastavení mozku (docs/brain-gate.md §1). Logika je v `backend/brain_opora/determinism/gate_setting.py`.

Přepínač brány čte kdokoli, mění ho jen člověk v UI (`require_human`, i při plné autonomii agentů).
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.brain_opora.determinism import gate_setting
from backend.brain_opora.determinism.gate_payloads import GateError, parse_body
from backend.canvas.activity_log import require_human


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

    return router
