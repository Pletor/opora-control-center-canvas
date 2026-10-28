"""Specifications-only proposal workflow; actor identity comes from the UI/agent session."""
from fastapi import APIRouter, Query, Request

from backend.canvas.activity_log import HumanRequired, require_authority
from backend.canvas.opora_acceptance import OporaAcceptance
from backend.canvas.opora_changesets import OporaChangesets


def create_opora_changeset_router(service):
    router = APIRouter(prefix="/api/oporahub", tags=["oporahub"])
    changesets = OporaChangesets(service)
    acceptance = OporaAcceptance(service)

    def author(request, *, human=False):
        actor = request.state.actor
        if human:
            require_authority(actor, "Přijetí zadání vyžaduje člověka v UI.")
        elif actor not in ("human", "agent"):
            raise HumanRequired(actor, "Chybí identita autora návrhu.")
        return {"kind": actor, "name": request.state.agent if actor == "agent" else "Člověk"}

    @router.get("/changesets/context")
    def context(project: str = Query(min_length=1, max_length=64),
                workspace: str = Query(min_length=1, max_length=64)):
        return changesets.context(project, workspace)

    @router.post("/baselines")
    def baseline(payload: dict, request: Request):
        return changesets.baseline(payload, author(request, human=True))

    @router.get("/revisions/{identifier}")
    def revision(identifier: str, project: str = Query(min_length=1, max_length=64),
                 workspace: str = Query(min_length=1, max_length=64)):
        return changesets.revision(project, workspace, identifier)

    @router.post("/changesets")
    def propose(payload: dict, request: Request):
        return changesets.create(payload, author(request))

    @router.get("/changesets")
    def history(project: str = Query(min_length=1, max_length=64),
                workspace: str = Query(min_length=1, max_length=64)):
        return changesets.list(project, workspace)

    @router.get("/changesets/{identifier}")
    def read(identifier: str, project: str = Query(min_length=1, max_length=64),
             workspace: str = Query(min_length=1, max_length=64)):
        return changesets.read(project, workspace, identifier)

    @router.post("/changesets/{identifier}/accept")
    def accept(identifier: str, payload: dict, request: Request):
        return acceptance.accept(identifier, payload, author(request, human=True))

    @router.post("/changesets/{identifier}/rebase")
    def rebase(identifier: str, payload: dict, request: Request):
        return changesets.rebase(identifier, payload, author(request))

    return router
