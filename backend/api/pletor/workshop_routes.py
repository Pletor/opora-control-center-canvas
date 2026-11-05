"""Routy Dílny D0 (docs/navrhy/2026-11-05-dilna-skillu.md §3a). Logika je v `backend/agi_pletor/pletor_opora_settings/`.

- `GET /api/pletor/workshop/tools` → `{tools: [{name, path, cases}]}`: funkce ze složky `tools/` v repu.
- `POST /api/pletor/workshop/tools/{name}/measure` (tělo `{}`: zápisová brána chce JSON) → `{name, passed, total,
  failed: [{name, got, expected}], durationMs, deterministic, error}`. Každý případ dvakrát v odděleném procesu; neznámá funkce 404, špatný název 422.
Jen pro člověka v UI a jen z tohoto počítače (prefix `/api/pletor` v `backend/app/remote_access.py`).
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.agi_pletor.pletor_opora_settings import workshop
from backend.brain_opora.determinism.gate_payloads import GateError, invalid
from backend.canvas.activity_log import require_human


def create_workshop_router(service, folder=workshop.TOOLS):
    router = APIRouter(prefix="/api/pletor/workshop", tags=["pletor"])

    @router.get("/tools")
    def tools(request: Request):
        require_human(request.state.actor, "Dílnu používá jen člověk v UI.")
        return {"tools": workshop.list_tools(folder)}

    @router.post("/tools/{name}/measure")
    def measure(name: str, request: Request):
        require_human(request.state.actor, "Funkce v Dílně měří jen člověk v UI.")
        try:
            return workshop.measure(folder, name)
        except ValueError as error:
            failure = invalid(str(error), "Příklad: POST /api/pletor/workshop/tools/rozdel_vety/measure")
        except LookupError as error:
            failure = GateError(404, "tool_not_found", str(error), "Seznam funkcí: GET /api/pletor/workshop/tools")
        return JSONResponse(failure.body(), status_code=failure.status)

    return router
