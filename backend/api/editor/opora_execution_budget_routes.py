"""Human budget controls; execution owners cannot impersonate human policy authority."""

from fastapi import APIRouter, Request

from backend.canvas.activity_log import require_human
from backend.canvas.opora_execution_budget_cancel import cancel
from backend.canvas.opora_execution_budgets import ExecutionBudgets


def create_execution_budget_router(service):
    router = APIRouter(prefix="/api/oporahub/execution-budgets", tags=["oporahub"])
    authority = ExecutionBudgets(service)

    def author(request):
        require_human(request.state.actor, "Execution budget controls require a human UI session.")
        return {"kind": "human", "name": "Člověk"}

    @router.get("")
    def context(request: Request, project: str, workspace: str, nodeId: str):
        return authority.context(project, workspace, nodeId, request.state.actor)

    @router.get("/history")
    def history(request: Request, project: str, workspace: str, nodeId: str):
        return authority.history(project, workspace, nodeId, request.state.actor)

    @router.post("")
    def configure(payload: dict, request: Request):
        return authority.configure(payload, author(request))

    @router.post("/{identifier}/cancel")
    def revoke(identifier: str, payload: dict, request: Request):
        return cancel(service, identifier, payload, author(request))

    return router
