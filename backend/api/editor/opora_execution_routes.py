"""Execution capability API: immutable assignments and bounded reported receipts."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.canvas.authority import can_act
from backend.canvas.opora_execution_context import prepare
from backend.canvas.opora_execution_deliver import deliver
from backend.canvas.opora_execution_results import ExecutionResults
from backend.canvas.opora_execution_start import start
from backend.canvas.opora_execution_steps import checkpoint
from backend.canvas.opora_local_merge import CommitOffBranch, InvalidCommit

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
        except InvalidCommit as exc:  # deliver → lokální sloučení (docs/lokalni-slouceni.md)
            return JSONResponse({"error": str(exc), "code": "invalid_commit"}, status_code=422)
        except CommitOffBranch as exc:
            return JSONResponse({"error": str(exc), "code": "commit_not_on_branch",
                                 "hint": "Slučte commit karty do aktuální větve projektu a odevzdejte znovu."}, status_code=409)
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

    def owner(request):
        name = getattr(request.state, "agent", None)
        if request.state.actor == "agent" and (not isinstance(name, str) or not name.strip()):
            raise ValueError("An identified execution owner is required.")
        return "agent:" + name if request.state.actor == "agent" else "human"

    @router.post("/start")
    def start_card(payload: dict, request: Request):
        # Složená akce: kontext v2 + hlavy z čerstvého stavu + claim + zadání (zefektivneni-opory.md §3.1).
        return call(request, lambda: start(executions, payload, owner(request)))

    @router.post("/{identifier}/deliver")
    def deliver_card(identifier: str, payload: dict, request: Request):
        # Složená akce: kroky, výsledek, lokální sloučení, kontroly a uzavření (zefektivneni-opory.md §3.2).
        def act():
            value = deliver(service, identifier, payload, request.headers.get("x-opora-execution-token"),
                            request.state.actor)
            if value["leaseRenewed"]:
                note_renewal(request, payload, value)
            return value
        return call(request, act)

    def note_renewal(request, payload, value):
        """Záznam činnosti: odevzdání přijalo vypršelé převzetí (epocha beze změny, nikdo kartu nepřevzal)."""
        from backend.canvas.activity_log import ActivityLog
        try:
            ActivityLog(service).record(
                actor=request.state.actor, agent=request.state.agent, method="POST", path=request.url.path,
                described={"project": payload["project"], "workspace": payload["workspace"], "nodeIds": [value["nodeId"]],
                           "summary": "lease_renewed_on_deliver execution=" + value["executionId"]},
                status=200)
        except Exception:  # noqa: BLE001 - záznam je doplněk, ne podmínka odevzdání
            return

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
