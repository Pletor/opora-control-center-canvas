"""`GET /api/oporahub/card-trail`: stopa práce jedné karty, jen čtení (docs/stopa-prace-karty.md)."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.canvas.card_trail import project_trail
from backend.canvas.card_trail_read import gather


def create_card_trail_router(service):
    router = APIRouter(prefix="/api/oporahub", tags=["oporahub"])

    @router.get("/card-trail")
    def card_trail(project: str, workspace: str, node: str, request: Request):
        # Stejná identita jako historie exekucí: stopa nese shrnutí a důkazy běhů.
        if getattr(request.state, "actor", None) not in ("human", "agent"):
            return JSONResponse({"error": "Execution identity is required.", "code": "identity_required"},
                                status_code=428)
        try:
            return project_trail(gather(service, project, workspace, node))
        except ValueError as error:
            return JSONResponse({"error": str(error), "code": "card_trail_unavailable"}, status_code=409)

    return router
