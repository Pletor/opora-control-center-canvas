"""Durable reconciliation HTTP controls require middleware-verified human identity."""
from fastapi import APIRouter, Query, Request

from backend.canvas.activity_log import HumanRequired
from backend.canvas.opora_reconciliation import OporaReconciliation


def create_opora_reconciliation_router(service):
    router = APIRouter(prefix="/api/oporahub/reconciliation", tags=["oporahub"])
    authority = OporaReconciliation(service)

    def human(request):
        actor = request.state.actor
        if actor != "human":
            raise HumanRequired(actor, "Only a verified human UI session may configure persistent tracking.")
        return {"kind": "human", "name": "Člověk"}

    @router.get("")
    def listing(request: Request, project: str = Query(min_length=1, max_length=64),
                workspace: str = Query(min_length=1, max_length=64)):
        return authority.list(project, workspace, request.state.actor)

    @router.get("/candidate")
    def candidate(request: Request, evidenceId: str, project: str = Query(min_length=1, max_length=64),
                  workspace: str = Query(min_length=1, max_length=64)):
        return authority.candidate(project, workspace, evidenceId, request.state.actor)

    @router.post("/bindings")
    def enroll(payload: dict, request: Request):
        return authority.enroll(payload, human(request))

    @router.post("/{binding_id}/control")
    def control(binding_id: str, payload: dict, request: Request):
        return authority.control(binding_id, payload, human(request))

    @router.get("/{binding_id}/history")
    def history(binding_id: str, project: str = Query(min_length=1, max_length=64),
                workspace: str = Query(min_length=1, max_length=64), cursor: str | None = None,
                attemptCursor: str | None = None):
        return authority.history(project, workspace, binding_id, cursor, attemptCursor)

    return router
