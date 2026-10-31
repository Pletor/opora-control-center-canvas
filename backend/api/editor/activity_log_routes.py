"""Rozhraní Editoru: záznam činnosti člověka a agentů (docs/zaznam-cinnosti.md)."""

from fastapi import APIRouter

from backend.canvas.activity_log import DEFAULT_LIMIT


def create_activity_log_router(activity_log):
    router = APIRouter(prefix="/api", tags=["activity-log"])

    @router.get("/activity-log")
    def read_activity_log(project: str = "", workspace: str = "", actor: str = "", nodeId: str = "",
                          limit: int = DEFAULT_LIMIT, before: int | None = None, agent: str = "",
                          since: str = "", until: str = ""):
        """Nejnovější první; `actor` = human | agent, bez něj obojí; `agent` = jméno agenta, `since` / `until` = ISO čas."""
        return activity_log.list(project=project, workspace=workspace, actor=actor, node_id=nodeId,
                                 limit=limit, before=before, agent=agent, since=since, until=until)

    return router
