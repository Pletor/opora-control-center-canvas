"""Editor API for explicitly requested, local-only semantic source retrieval."""

from fastapi import APIRouter, Query

from backend.project.workspace.workspace_sources import WorkspaceSources
from backend.semantic_retrieval.service import SemanticRetrieval


def create_semantic_router(service, *, semantic_service=None):
    """Factory integration point: the app factory includes this router when approved by the coordinator."""
    router = APIRouter(prefix="/api/semantic-search", tags=["semantic-search"])
    retrieval = semantic_service or SemanticRetrieval(WorkspaceSources(service))

    @router.get("/status")
    def status(project: str = Query(min_length=1, max_length=200), workspace: str = Query(min_length=1, max_length=200)):
        return retrieval.status(project, workspace)

    @router.post("/query")
    def query(payload: dict):
        return retrieval.query(payload)

    return router
