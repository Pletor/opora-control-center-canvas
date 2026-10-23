"""Lens plánu (docs/plan-lens.md): `GET /api/oporahub/plan-lens`, plán z plátna jako graf PR Lens jen ke čtení."""
from fastapi import APIRouter, Query, Request

from backend.api.editor.opora_review_lens_routes import SCOPE, error
from backend.api.http_etag import conditional, etag_of
from backend.canvas.opora_execution_validation import validate
from backend.canvas.plan_lens import AreaNotFound
from backend.canvas.plan_lens_source import PlanLensReader
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State


def create_plan_lens_router(service, desktop_state=None):
    router = APIRouter(prefix="/api/oporahub", tags=["oporahub"])
    reader = PlanLensReader(service, desktop_state or getattr(service, "desktop_v3_state", None) or DesktopV3State(service))

    @router.get("/plan-lens")
    def read(request: Request, project: str = Query(**SCOPE), workspace: str = Query(**SCOPE),
             area: str | None = Query(default=None, min_length=1, max_length=80)):
        """Stejná identita jako `GET /review-lens` (člověk nebo `X-Opora-Actor`); ETag z razítka vstupů → 304."""
        actor, name = request.state.actor, getattr(request.state, "agent", None)
        if actor not in ("human", "agent") or (actor == "agent" and (not isinstance(name, str) or not name.strip())):
            return error("Review identity is required.", "identity_required", 428)
        try:
            validate({"project": project, "workspace": workspace}, set())
        except ValueError as exc:
            return error(str(exc), "invalid_request", 400)
        try:
            stamp, body = reader.read(project, workspace, area)
        except AreaNotFound as exc:
            return error(str(exc), "area_not_found", 404)
        return conditional(request, etag_of(*stamp), lambda: body)

    return router
