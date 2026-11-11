"""`GET /api/oporahub/plan-reality`: folie z kódu (docs/navrhy/2026-11-11-platno-3-folie.md, F1), jen čtení."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.canvas import plan_reality
from backend.canvas.opora_change_validation import scope


def create_plan_reality_router(service, root=None):
    router = APIRouter(prefix="/api/oporahub", tags=["oporahub"])

    @router.get("/plan-reality")
    def read_plan_reality(project: str, workspace: str, request: Request, nodeId: str | None = None):
        # Stejná identita jako živá karta: čte člověk, srdce i dělník.
        if getattr(request.state, "actor", None) not in ("human", "agent"):
            return JSONResponse({"error": "Execution identity is required.", "code": "identity_required"},
                                status_code=428)
        try:
            scope({"project": project, "workspace": workspace})
            found = root or plan_reality.root_of(service, project, workspace)
            if nodeId is None:
                return plan_reality.summary(service, project, workspace, found)
            result = plan_reality.for_card(service, project, workspace, nodeId, found)
        except (ValueError, KeyError) as error:
            return JSONResponse({"error": str(error), "code": "plan_reality_unavailable"}, status_code=409)
        if result is None:
            return JSONResponse({"error": "Projekt nemá známý repozitář.", "code": "repository_unknown"},
                                status_code=409)
        return {"nodeId": nodeId, **result, "counts": plan_reality.counts(result)}

    return router
