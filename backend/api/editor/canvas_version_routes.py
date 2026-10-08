"""Rozhraní Editoru: uložené verze plátna (docs/verze-platna.md, „Backend“)."""

from fastapi import APIRouter, Request

from backend.canvas.activity_log import require_human
from backend.editor.canvas_versions.canvas_versions import CanvasVersions


def create_canvas_version_router(service, desktop_state=None):
    router = APIRouter(prefix="/api", tags=["canvas"])
    versions = CanvasVersions(service, desktop_state)

    @router.get("/canvas-versions")
    def canvas_versions(project: str = "draft", workspace: str = "draft", versionId: str | None = None):
        return versions.read(project, workspace, versionId) if versionId is not None else versions.list(project, workspace)

    @router.post("/canvas-versions")
    def save_canvas_version(payload: dict, request: Request):
        return versions.save(payload, actor=request.state.actor)

    @router.post("/canvas-versions/restore")
    def restore_canvas_version(payload: dict, request: Request):
        # Obnova přepisuje celé plátno včetně uzavření; smí ji jen člověk (upgrade-opora #30).
        require_human(request.state.actor, "Obnovení verze plátna provádí člověk v UI.")
        # Neuložené změny se před obnovením samy uloží jako verze „<autor> (před obnovením)“.
        return versions.restore(payload)

    return router
