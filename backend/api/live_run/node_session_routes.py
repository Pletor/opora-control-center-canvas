"""Rozhraní Live Run: živé session agentů navázané na uzel."""

import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.live_run.node_session_sources import ClaudeLaneSource, HermesSessionSource
from backend.live_run.node_sessions import NodeSessions


def create_node_sessions_router(service, *, hermes_source=None, claude_source=None, clock=None):
    hermes = hermes_source or HermesSessionSource(
        os.environ.get("OPORA_HERMES_API_URL") or None,
        os.environ.get("OPORA_HERMES_API_KEY") or None,
    )
    claude = claude_source or ClaudeLaneSource(os.environ.get("OPORA_NODE_SESSION_LANES_ROOT") or None)
    sessions = NodeSessions(service, hermes=hermes, claude=claude, clock=clock)
    service.node_sessions = sessions

    router = APIRouter(prefix="/api/node-sessions", tags=["node-sessions"])

    @router.get("")
    def list_sessions(project: str, workspace: str, nodeId: str | None = None):
        try:
            return sessions.list(project, workspace, nodeId)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=409)

    @router.post("/bind")
    def bind(payload: dict):
        try:
            return sessions.bind(payload)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=409)

    return router
