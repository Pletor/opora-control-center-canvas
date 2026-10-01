"""Read-only, LSP-first editor code-intelligence endpoints.

Factory registration is intentionally left to the coordinating backend writer:
`app.include_router(create_code_intelligence_router(service))`.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.code_intelligence import CodeIntelligence, QueryRequest
from backend.paths import REPO_ROOT
from backend.project.workspace.workspace_sources import WorkspaceSources

_QUERY_KEYS = {"project", "workspace", "language", "path", "operation", "line", "character"}


def create_code_intelligence_router(service, *, intelligence=None):
    router = APIRouter(prefix="/api/code-intelligence", tags=["code-intelligence"])
    adapter = intelligence or CodeIntelligence(
        WorkspaceSources(service).root,
        # Launchers may resolve their npm dependencies from Opora while rootUri remains workspace-scoped.
        server_cwd=REPO_ROOT,
    )

    @router.get("/status")
    def status(project: str, workspace: str):
        # This only tests static launcher configuration; it never constructs a protocol/process.
        return adapter.status(project, workspace)

    @router.post("/query")
    def query(payload: dict):
        if not isinstance(payload, dict) or set(payload) != _QUERY_KEYS:
            return JSONResponse(
                {"error": "LSP dotaz vyžaduje přesně project, workspace, language, path, operation, line a character."},
                status_code=409,
            )
        return adapter.query(QueryRequest(**payload))

    return router
