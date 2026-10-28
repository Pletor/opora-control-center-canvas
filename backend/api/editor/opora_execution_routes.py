"""Execution capability API: immutable assignments and bounded reported receipts."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.canvas.authority import can_act
from backend.canvas.opora_execution_context import prepare
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.opora_execution_steps import checkpoint

ASSIGNMENT_VIEWS = ("include", "omit")


def lease_view(record, view):
    """`assignment=omit`: claim/heartbeat without the immutable assignment (read it once from /assignment).

    The default stays `include` until every client sends `omit` (agent-office M5); `contextVersion`
    is lifted to the top level so a slim client can still check the claimed context.
    """
    if view == "include" or not isinstance(record, dict) or "assignment" not in record:
        return record
    value = {key: item for key, item in record.items() if key != "assignment"}
    return value | {"contextVersion": record["assignment"].get("contextVersion")}


def create_opora_execution_router(service):
    router = APIRouter(prefix="/api/oporahub/executions", tags=["oporahub"])
    executions = ExecutionResults(service)

    def call(request, action, view="include"):
        if request.state.actor not in ("human", "agent"):
            return JSONResponse({"error": "Execution identity is required.", "code": "identity_required"}, status_code=428)
        if view not in ASSIGNMENT_VIEWS:  # Refused before any claim or renewal happens.
            return JSONResponse({"error": "assignment must be include or omit.", "code": "execution_conflict"}, status_code=409)
        try:
            return action()
        except ValueError as exc:
            if hasattr(exc, "body"):  # InvalidPayload (422) / NextStep (409 s hint), backend/canvas/payload_errors.py
                return JSONResponse(exc.body(), status_code=exc.status)
            # Claim readiness refusals carry their own code (plan_steps_missing, blocked_by_predecessor).
            return JSONResponse({"error": str(exc), "code": getattr(exc, "code", "execution_conflict")}, status_code=409)

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
        return call(request, lambda: executions.history(project, workspace, nodeId) | {"canCancel": can_act(request.state.actor)})

    @router.get("/{identifier}/results")
    def receipts(identifier: str, project: str, workspace: str, request: Request):
        return call(request, lambda: executions.receipts(identifier, project, workspace))

    @router.post("/claim")
    def claim(payload: dict, request: Request, assignment: str = "include"):
        def create():
            name = getattr(request.state, "agent", None)
            if request.state.actor == "agent" and (not isinstance(name, str) or not name.strip()):
                raise ValueError("An identified execution owner is required.")
            return lease_view(executions.claim(payload, "agent:" + name if request.state.actor == "agent" else "human"), assignment)
        return call(request, create, assignment)

    @router.get("/{identifier}/assignment")
    def assignment(identifier: str, project: str, workspace: str, request: Request):
        return call(request, lambda: executions.read_assignment(identifier, project, workspace,
                                                               request.headers.get("x-opora-execution-token")))

    @router.post("/{identifier}/heartbeat")
    def heartbeat(identifier: str, payload: dict, request: Request, assignment: str = "include"):
        return call(request, lambda: lease_view(executions.heartbeat(identifier, payload), assignment), assignment)

    @router.post("/{identifier}/release")
    def release(identifier: str, payload: dict, request: Request):
        return call(request, lambda: executions.release(identifier, payload))

    @router.post("/{identifier}/steps")
    def steps(identifier: str, payload: dict, request: Request):
        return call(request, lambda: checkpoint(executions, identifier, payload))

    @router.post("/{identifier}/results")
    def results(identifier: str, payload: dict, request: Request):
        return call(request, lambda: executions.submit(identifier, payload))

    return router
