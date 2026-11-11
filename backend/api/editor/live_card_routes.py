"""`GET /api/oporahub/live-card`: živá karta pro líc i rub (docs/navrhy/2026-11-11-platno-3-folie.md, K1), jen čtení."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.canvas import live_card
from backend.paths import REPO_ROOT


def create_live_card_router(service, pletor=None, root=None):
    router = APIRouter(prefix="/api/oporahub", tags=["oporahub"])

    @router.get("/live-card")
    def read_live_card(project: str, workspace: str, nodeId: str, request: Request):
        # Stejná identita jako stopa karty: karta nese běhy a jejich důkazy.
        if getattr(request.state, "actor", None) not in ("human", "agent"):
            return JSONResponse({"error": "Execution identity is required.", "code": "identity_required"},
                                status_code=428)
        try:
            facts = live_card.gather(service, project, workspace, nodeId, root=root or REPO_ROOT,
                                     folder=getattr(pletor, "folder", None))
        except ValueError as error:
            return JSONResponse({"error": str(error), "code": "live_card_unavailable"}, status_code=409)
        return live_card.compose(facts)

    return router
