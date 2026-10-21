"""Derived plan data over HTTP: card history and blame from accepted changesets (no local copy)."""
from fastapi import APIRouter, Query, Request

from backend.canvas.activity_log import require_human
from backend.canvas.opora_derived_history import DerivedHistory


def create_opora_history_router(service):
    router = APIRouter(prefix="/api/oporahub", tags=["oporahub"])
    derived = DerivedHistory(service)

    @router.get("/history/card/{card_id}")
    def history(card_id: str, project: str = Query(min_length=1, max_length=64),
                workspace: str = Query(min_length=1, max_length=64)):
        return derived.history(project, workspace, card_id)

    @router.get("/blame/card/{card_id}")
    def blame(card_id: str, project: str = Query(min_length=1, max_length=64),
              workspace: str = Query(min_length=1, max_length=64)):
        return derived.blame(project, workspace, card_id)

    @router.post("/history/rebuild")
    def rebuild(payload: dict, request: Request):
        require_human(request.state.actor, "Přepočet odvozené historie spouští člověk.")
        return derived.rebuild(payload.get("project"), payload.get("workspace"))

    return router
