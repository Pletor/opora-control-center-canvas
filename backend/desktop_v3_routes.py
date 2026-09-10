"""HTTP kontrakt Desktop v3: paměť projektu, stav uzlů, podklady pro agenta."""

from fastapi import APIRouter


def create_desktop_v3_router(state, packets, handoffs):
    router = APIRouter(prefix="/api/desktop-v3", tags=["desktop-v3"])

    @router.get("/state")
    def read_state(project: str, workspace: str):
        return state.read(project, workspace)

    @router.post("/state")
    def save_state(payload: dict):
        return state.save(payload)

    @router.post("/packet/preview")
    def packet_preview(payload: dict):
        return packets.build(payload)

    @router.post("/packet/snapshot")
    def packet_snapshot(payload: dict):
        stored = packets.snapshot(payload)
        return {key: stored[key] for key in ("id", "digest", "packet", "createdAt")}

    @router.get("/packet/snapshots/{snapshot_id}")
    def packet_snapshot_read(snapshot_id: str, project: str, workspace: str):
        stored = packets.load(snapshot_id, project, workspace)
        return {key: stored[key] for key in ("id", "digest", "packet", "createdAt")}

    @router.post("/packet/snapshots/{snapshot_id}/prepare")
    def packet_prepare(snapshot_id: str, payload: dict):
        if not isinstance(payload, dict) or set(payload) != {"project", "workspace", "task"}:
            raise ValueError("Příprava vyžaduje project, workspace a task.")
        snapshot = packets.load(snapshot_id, payload["project"], payload["workspace"])
        return handoffs.prepare_from_snapshot(snapshot, payload["task"])

    return router
