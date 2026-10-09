"""Rozhraní Projektu: strom zdrojů, otevření souboru a dokumentace k cestám."""

from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, JSONResponse

from backend.project.workspace.workspace_documents import WorkspaceDocuments
from backend.project.workspace.workspace_sources import (
    SourceMissing,
    WorkspaceSources,
    relative_path,
)

IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
               ".webp": "image/webp", ".svg": "image/svg+xml"}


def create_workspace_router(service):
    router = APIRouter(prefix="/api/workspace")
    sources = WorkspaceSources(service)
    documents = WorkspaceDocuments(service, sources)

    @router.post("/open-file")
    def open_file(payload: dict):
        return sources.open_file(payload)

    @router.get("/tree")
    def tree(project: str, workspace: str, path: str = "", offset: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=500), visibility: Literal['all', 'working'] = 'all'):
        return sources.tree(project, workspace, path, offset, limit, visibility)

    @router.get("/image")
    def image(project: str, workspace: str, path: str):
        """Náhled obrázku ze zdroje projektu pro strom obsahu; jen obrázkové přípony, jen uvnitř kořene."""
        relative_path(path)
        suffix = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
        if suffix not in IMAGE_TYPES:
            return JSONResponse({"error": "Náhled je jen pro obrázky (png, jpg, gif, webp, svg)."}, status_code=415)
        try:
            root = sources.root(project, workspace)
            if root is None:
                raise SourceMissing("Projekt nemá zdrojový kořen.")
            target = sources.target(root, path)
        except (SourceMissing, FileNotFoundError):
            return JSONResponse({"error": "Obrázek ve zdroji projektu není."}, status_code=404)
        if not target.is_file():
            return JSONResponse({"error": "Cesta není soubor."}, status_code=404)
        return FileResponse(target, media_type=IMAGE_TYPES[suffix], headers={"Cache-Control": "no-store"})

    @router.get("/document")
    def document(project: str, workspace: str, path: str = ""):
        return documents.read(project, workspace, path)

    @router.post("/document")
    def save_document(payload: dict):
        return documents.save(payload)

    return router
