"""HTTP kontrakt izolovaných dokumentačních handoffů."""

from fastapi import APIRouter


def create_task_handoff_router(handoffs):
    router = APIRouter(prefix="/api/task-handoffs", tags=["task-handoffs"])

    @router.get("/capabilities")
    def capabilities(project: str):
        return handoffs.capabilities(project)

    @router.post("/prepare")
    def prepare(payload: dict):
        return handoffs.prepare(payload)

    @router.get("")
    def list_runs(project: str, workspace: str):
        return handoffs.list(project, workspace)

    @router.get("/{handoff_id}/export")
    def export(handoff_id: str):
        return handoffs.export(handoff_id)

    @router.get("/{handoff_id}")
    def get(handoff_id: str):
        return handoffs.get(handoff_id)

    @router.post("/{handoff_id}/start")
    def start(handoff_id: str, payload: dict):
        return handoffs.start(handoff_id, payload)

    @router.post("/{handoff_id}/stop")
    def stop(handoff_id: str, payload: dict):
        return handoffs.stop(handoff_id, payload)

    return router
