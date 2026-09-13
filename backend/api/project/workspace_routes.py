"""Rozhraní Projektu: strom zdrojů, otevření souboru a dokumentace k cestám."""

from typing import Literal

from fastapi import APIRouter, Query

from backend.project.workspace.workspace_documents import WorkspaceDocuments
from backend.project.workspace.workspace_sources import WorkspaceSources


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

    @router.get("/document")
    def document(project: str, workspace: str, path: str = ""):
        return documents.read(project, workspace, path)

    @router.post("/document")
    def save_document(payload: dict):
        return documents.save(payload)

    return router
