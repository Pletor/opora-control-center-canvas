"""Separate immutable graph-addition proposals; accepted revisions share the plan chain."""
from fastapi import APIRouter, Request

from backend.api.brain_opora.writer import heart_project
from backend.canvas.activity_labels import created_nodes, proposal_trace
from backend.canvas.activity_log import HumanRequired, note, note_from, require_authority
from backend.canvas.opora_graph_acceptance import OporaGraphAcceptance
from backend.canvas.opora_graph_change_plan import heart_scope
from backend.canvas.opora_graph_proposals import OporaGraphProposals


def create_opora_graph_router(service):
    router = APIRouter(prefix="/api/oporahub/graph-proposals", tags=["oporahub"])
    proposals, acceptance = OporaGraphProposals(service), OporaGraphAcceptance(service)

    def author(request, *, human=False):
        actor = request.state.actor
        if human:
            require_authority(actor, "Graph additions require human acceptance in the UI.")
        elif actor not in ("human", "agent"):
            raise HumanRequired(actor, "A proposal author is required.")
        return {"kind": actor, "name": request.state.agent if actor == "agent" else "Člověk"}

    @router.get("/context")
    def context(project: str, workspace: str):
        return proposals.context(project, workspace)

    @router.get("")
    def history(project: str, workspace: str):
        return proposals.list(project, workspace)

    @router.post("")
    def create(payload: dict, request: Request):
        if heart_project(request):
            heart_scope(payload.get("plan"))  # srdce mění u existujícího uzlu jen memberOf a order (422 heart_edit_scope)
        result = proposals.create(payload, author(request))
        note(request, created_nodes(result))  # nové uzly mají ID až v odpovědi (stopa karty, docs/zaznam-cinnosti.md)
        return result

    @router.get("/{identifier}")
    def read(identifier: str, project: str, workspace: str):
        return proposals.read(project, workspace, identifier)

    @router.post("/{identifier}/rebase")
    def rebase(identifier: str, payload: dict, request: Request):
        return proposals.rebase(identifier, payload, author(request))

    @router.post("/{identifier}/accept")
    def accept(identifier: str, payload: dict, request: Request):
        result = acceptance.accept(identifier, payload, author(request, human=True))
        # Stopa karty: uzly a popisek přijatého návrhu z jeho uloženého záznamu.
        note_from(request, lambda: proposal_trace(proposals.read(payload["project"], payload["workspace"], identifier)))
        return result

    return router
