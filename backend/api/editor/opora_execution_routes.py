"""Execution capability API: immutable assignments and bounded reported receipts."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.canvas.opora_execution_context import prepare
from backend.canvas.opora_execution_results import ExecutionResults


def create_opora_execution_router(service):
    router = APIRouter(prefix="/api/oporahub/executions", tags=["oporahub"])
    executions = ExecutionResults(service)

    def call(request, action):
        if request.state.actor not in ("human", "agent"):
            return JSONResponse({"error": "Execution identity is required.", "code": "identity_required"}, status_code=428)
        try:
            return action()
        except ValueError as exc:
            return JSONResponse({"error": str(exc), "code": "execution_conflict"}, status_code=409)

    @router.get("/context")
    def context(project: str, workspace: str, nodeId: str):
        return executions.context(project, workspace, nodeId)

    @router.post("/context")
    def prepare_context(payload: dict, request: Request):
        def create():
            name = getattr(request.state, "agent", None)
            if request.state.actor == "agent" and (not isinstance(name, str) or not name.strip()):
                raise ValueError("An identified execution owner is required.")
            return prepare(executions, payload)
        return call(request, create)

    @router.get("")
    def history(project: str, workspace: str, request: Request, nodeId: str | None = None):
        return call(request, lambda: executions.history(project, workspace, nodeId) | {"canCancel": request.state.actor == "human"})

    @router.get("/{identifier}/results")
    def receipts(identifier: str, project: str, workspace: str, request: Request):
        return call(request, lambda: executions.receipts(identifier, project, workspace))

    @router.post("/claim")
    def claim(payload: dict, request: Request):
        def create():
            name = getattr(request.state, "agent", None)
            if request.state.actor == "agent" and (not isinstance(name, str) or not name.strip()):
                raise ValueError("An identified execution owner is required.")
            return executions.claim(payload, "agent:" + name if request.state.actor == "agent" else "human")
        return call(request, create)

    @router.get("/{identifier}/assignment")
    def assignment(identifier: str, project: str, workspace: str, request: Request):
        return call(request, lambda: executions.read_assignment(identifier, project, workspace,
                                                               request.headers.get("x-opora-execution-token")))

    @router.post("/{identifier}/heartbeat")
    def heartbeat(identifier: str, payload: dict, request: Request):
        return call(request, lambda: executions.heartbeat(identifier, payload))

    @router.post("/{identifier}/release")
    def release(identifier: str, payload: dict, request: Request):
        return call(request, lambda: executions.release(identifier, payload))

    @router.post("/{identifier}/results")
    def results(identifier: str, payload: dict, request: Request):
        return call(request, lambda: executions.submit(identifier, payload))

    return router
