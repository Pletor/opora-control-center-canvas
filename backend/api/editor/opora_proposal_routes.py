"""Additive proposal API; existing commit readers remain compatible."""

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from backend.canvas.opora_proposals import OporaProposals


def create_opora_proposal_router(service, hub):
    router = APIRouter(prefix="/api/oporahub", tags=["oporahub"])
    proposals = OporaProposals(service, hub)

    @router.get("/context")
    def context(project: str = Query(min_length=1, max_length=64),
                workspace: str = Query(min_length=1, max_length=64),
                scope: str = Query(min_length=1, max_length=80)):
        return proposals.context((project, workspace, scope))

    @router.post("/proposals")
    def propose(payload: dict, request: Request):
        # Attribution comes from the existing session/actor middleware, never payload.by.
        actor = request.state.actor
        if actor not in ("agent", "human"):
            return JSONResponse({"error": "Chybí identita autora návrhu.",
                                 "humanRequired": True}, status_code=428)
        by = {"kind": actor, "name": request.state.agent if actor == "agent" else "Člověk"}
        return proposals.propose(
            (payload.get("project"), payload.get("workspace"), payload.get("scope")), payload, by)

    @router.get("/diff")
    def diff(project: str = Query(min_length=1, max_length=64),
             workspace: str = Query(min_length=1, max_length=64),
             scope: str = Query(min_length=1, max_length=80),
             before: str = Query(min_length=40, max_length=40),
             after: str = Query(min_length=40, max_length=40)):
        return proposals.diff((project, workspace, scope), before, after)

    return router
