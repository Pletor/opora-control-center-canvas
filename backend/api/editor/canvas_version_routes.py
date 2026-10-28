"""Rozhraní Editoru: uložené verze plátna (docs/verze-platna.md, „Backend“)."""

from fastapi import APIRouter, Request

from backend.api.http_etag import conditional, etag_of
from backend.canvas.activity_log import require_authority
from backend.editor.canvas_versions.canvas_versions import CanvasVersions


def create_canvas_version_router(service, desktop_state=None):
    router = APIRouter(prefix="/api", tags=["canvas"])
    versions = CanvasVersions(service, desktop_state)

    @router.get("/canvas-versions")
    def canvas_versions(request: Request, project: str = "draft", workspace: str = "draft", versionId: str | None = None):
        if versionId is not None:
            return versions.read(project, workspace, versionId)
        # Výpis se drží v cache podle tokenu dat; ETag z tokenu obsahu, stavu „dirty“ a ID verzí (karta P3).
        listed = versions.list(project, workspace)
        tag = etag_of("canvas-versions", project, workspace, listed["currentToken"], listed["dirty"],
                      [item["id"] for item in listed["versions"]])
        return conditional(request, tag, lambda: listed)

    @router.get("/canvas-versions/head")
    def canvas_versions_head(request: Request, project: str = "draft", workspace: str = "draft"):
        """Levná hlava pro polling: jen `currentToken` a `dirty`; výpis verzí si klient stáhne,
        až se token změní (karta P3)."""
        head = versions.head(project, workspace)
        return conditional(request, etag_of("canvas-versions-head", project, workspace, head), lambda: head)

    @router.post("/canvas-versions")
    def save_canvas_version(payload: dict, request: Request):
        return versions.save(payload, actor=request.state.actor)

    @router.post("/canvas-versions/restore")
    def restore_canvas_version(payload: dict, request: Request):
        # Obnova přepisuje celé plátno včetně uzavření; smí ji jen člověk (upgrade-opora #30).
        require_authority(request.state.actor, "Obnovení verze plátna provádí člověk v UI.")
        # Neuložené změny se před obnovením samy uloží jako verze „<autor> (před obnovením)“.
        return versions.restore(payload)

    return router
