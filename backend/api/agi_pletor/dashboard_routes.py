"""Routy velínu Pletora, jen čtení (docs/navrhy/2026-11-05-pletor-opora-dashboard.md, V2 a V3). Logika je v
`backend/agi_pletor/dashboard/`. Vše jen pro člověka v UI a jen z tohoto počítače (`/api/pletor`).

- `GET /api/pletor/heart?project&workspace` → `{status, queue: [{workspace, pending}], batches, gate, brain}`.
- `GET /api/pletor/context?project&workspace` → `{text, sections: [{title, chars, cap, truncated}]}`.
- `GET /api/pletor/messages?project&workspace&limit=50&q=` → `{messages: [{role, text, at}], total}` (limit 1–500).
- `GET /api/pletor/monitoring?project` → `{hosts, events, enabled}`.
Zdroj, který selže, vrátí v sekci `{error}`; routa nikdy 500.
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.agi_pletor import context
from backend.agi_pletor.dashboard import views
from backend.agi_pletor.dashboard.heart_view import heart_view, safe
from backend.api.agi_pletor.pletor_routes import _check
from backend.brain_opora.determinism.gate_payloads import GateError, invalid
from backend.canvas.activity_log import require_human

HUMAN = "Velín Pletora čte jen člověk v UI."


def create_dashboard_router(service, heart, pletor):
    router = APIRouter(prefix="/api/pletor", tags=["pletor"])

    def guarded(request, project, workspace, read):
        require_human(request.state.actor, HUMAN)
        try:
            _check(service, project, workspace)
            return read()
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)

    @router.get("/heart")
    def heart_state(request: Request, project: str = "", workspace: str = ""):
        return guarded(request, project, workspace, lambda: heart_view(service, heart, project, workspace))

    @router.get("/context")
    def context_state(request: Request, project: str = "", workspace: str = ""):
        return guarded(request, project, workspace, lambda: {
            "text": safe(lambda: context.build_context(service, heart, project, workspace)),
            "sections": safe(lambda: context.sections_report(service, heart, project, workspace))})

    @router.get("/messages")
    def messages_state(request: Request, project: str = "", workspace: str = "", limit: int = 50, q: str = ""):
        def read():
            if not 1 <= limit <= 500:
                raise invalid("limit je číslo 1–500.", "Příklad: ?limit=50")
            return views.messages_view(pletor.folder, project, workspace, limit, q)

        return guarded(request, project, workspace, read)

    @router.get("/monitoring")
    def monitoring_state(request: Request, project: str = ""):
        return guarded(request, project, "main", lambda: views.monitoring_view(service, project))

    return router
