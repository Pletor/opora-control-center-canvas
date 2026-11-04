"""Routy Pletora (docs/navrhy/2026-11-04-pletor-jarvis.md, P1). Logika je v `backend/pletor/`.

- `POST /api/pletor/messages {project, workspace, text}` → `{reply, actions: [{type, text, ok, detail?}]}`.
- `GET /api/pletor/state?project&workspace` → `{messages, heart, escalations, brain: {brain, model, available}}`.
- `POST /api/pletor/brain {brain: claude | ollama, model?}` → `{ok, reply, brain}` (P2; selhání = `ok: false`).
Všechny jen pro člověka v UI a jen z tohoto počítače (`/api/pletor` v `backend/app/remote_access.py`).
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.api.pletor import models
from backend.brain_opora.determinism.gate_payloads import GateError, invalid
from backend.canvas.activity_log import require_human
from backend.canvas.graph import valid_id
from backend.pletor import brains


def _check(service, project, workspace):
    if not (project == "draft" or valid_id(project)) or not valid_id(workspace):
        raise invalid("Neplatné ID projektu nebo pracovního prostoru.", "Přidejte project=<id>&workspace=<id>.")
    if not service.project_exists(project):
        raise GateError(404, "project_not_found", "Projekt neexistuje.", "ID projektu najdete v GET /api/bootstrap.")


def create_pletor_router(service, pletor):
    router = APIRouter(prefix="/api/pletor", tags=["pletor"])

    @router.post("/messages", response_model=models.PletorReplyOut)
    async def message(body: models.PletorMessageIn, request: Request):
        require_human(request.state.actor, "S Pletorem mluví jen člověk v UI.")
        try:
            _check(service, body.project, body.workspace)
            if not body.text.strip() or "\0" in body.text:
                raise invalid("text je neprázdný text.", 'Příklad: {"project": "<id>", "workspace": "main", "text": "…"}')
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)
        return await run_in_threadpool(pletor.message, body.project, body.workspace, body.text.strip())

    @router.get("/state", response_model=models.PletorStateOut)
    def state(request: Request, project: str = "", workspace: str = ""):
        require_human(request.state.actor, "Rozhovor s Pletorem čte jen člověk v UI.")
        try:
            _check(service, project, workspace)
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)
        return {**pletor.state(project, workspace), "brain": brains.status(pletor.folder, pletor.transport)}

    @router.post("/brain", response_model=models.PletorBrainOut)
    def brain(body: models.PletorBrainIn, request: Request):
        require_human(request.state.actor, "Mozek Pletora přepíná jen člověk v UI.")
        ok, reply = brains.switch(pletor.folder, body.brain, body.model, pletor.transport)
        return {"ok": ok, "reply": reply, "brain": brains.status(pletor.folder, pletor.transport)}

    return router
