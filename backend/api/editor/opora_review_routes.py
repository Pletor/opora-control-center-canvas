"""Read-only GitHub imports; initiator attribution comes from middleware, never JSON."""
from fastapi import APIRouter, Query, Request

from backend.canvas.activity_log import HumanRequired
from backend.canvas.opora_review_evidence import OporaReviewEvidence


def create_opora_review_router(service, reader=None):
    router = APIRouter(prefix="/api/oporahub/github-evidence", tags=["oporahub"])
    evidence = OporaReviewEvidence(service, reader)

    @router.get("")
    def history(project: str = Query(min_length=1, max_length=64),
                workspace: str = Query(min_length=1, max_length=64)):
        return evidence.list(project, workspace)

    @router.post("")
    def observe(payload: dict, request: Request):
        actor = request.state.actor
        if actor not in ("human", "agent"):
            raise HumanRequired(actor, "Chybí identita iniciátora načtení.")
        by = {"kind": actor, "name": request.state.agent if actor == "agent" else "Člověk"}
        return evidence.observe(payload, by)

    @router.get("/{identifier}")
    def read(identifier: str, project: str = Query(min_length=1, max_length=64),
             workspace: str = Query(min_length=1, max_length=64)):
        return evidence.read(project, workspace, identifier)

    return router
