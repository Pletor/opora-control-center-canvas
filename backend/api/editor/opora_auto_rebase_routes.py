"""Auto-rebase conflicts and sparse-context enrollment; acceptance is never offered here."""
from fastapi import APIRouter, Query, Request

from backend.canvas import opora_sparse_enrollment as sparse
from backend.canvas.activity_log import HumanRequired, require_human
from backend.canvas.opora_auto_rebase import AutoRebase


def create_opora_auto_rebase_router(service):
    router = APIRouter(prefix="/api/oporahub", tags=["oporahub"])
    rebase = AutoRebase(service)

    def author(request):
        actor = request.state.actor
        if actor not in ("human", "agent"):
            raise HumanRequired(actor, "Chybí identita autora.")
        return {"kind": actor, "name": request.state.agent if actor == "agent" else "Člověk"}

    @router.get("/auto-rebase/conflicts")
    def conflicts(project: str = Query(min_length=1, max_length=64),
                  workspace: str = Query(min_length=1, max_length=64), status: str | None = None):
        return rebase.conflicts(project, workspace, status)

    @router.get("/auto-rebase/conflicts/{conflict_id}")
    def conflict(conflict_id: str, project: str = Query(min_length=1, max_length=64),
                 workspace: str = Query(min_length=1, max_length=64)):
        return rebase.conflict(project, workspace, conflict_id)

    @router.post("/auto-rebase/conflicts/{conflict_id}/resolve")
    def resolve(conflict_id: str, payload: dict, request: Request):
        return rebase.resolve(conflict_id, payload, author(request))

    @router.post("/auto-rebase/run")
    def run(payload: dict, request: Request):
        author(request)
        return rebase.run(payload.get("project"), payload.get("workspace"))

    @router.get("/sparse-context/enrollment")
    def enrollment(project: str = Query(min_length=1, max_length=64),
                   workspace: str = Query(min_length=1, max_length=64)):
        return sparse.status(service, project, workspace)

    @router.post("/sparse-context/backfill")
    def backfill(payload: dict, request: Request):
        dry_run = payload.get("dryRun", True)
        if type(dry_run) is not bool:
            raise ValueError("dryRun must be a boolean.")
        if not dry_run:
            require_human(request.state.actor, "Zápis backfillu sparse kontextu spouští člověk.")
        return sparse.backfill(service, payload.get("project"), payload.get("workspace"), dry_run=dry_run)

    return router
