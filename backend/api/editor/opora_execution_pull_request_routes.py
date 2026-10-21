"""Execution -> PR link API: lease-fenced agent or human session; GitHub stays read-only."""
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from backend.canvas.opora_execution_pull_requests import ExecutionPullRequestLinks, LinkMissing


def create_execution_pull_request_router(service, links=None):
    router = APIRouter(prefix="/api/oporahub/executions", tags=["oporahub"])
    links = links or ExecutionPullRequestLinks(service)

    def call(request, action):
        if request.state.actor not in ("human", "agent"):
            return JSONResponse({"error": "Execution identity is required.", "code": "identity_required"}, status_code=428)
        try:
            return action()
        except LinkMissing as exc:
            return JSONResponse({"error": str(exc), "code": "pull_request_not_linked"}, status_code=404)
        except ValueError as exc:
            return JSONResponse({"error": str(exc), "code": "execution_conflict"}, status_code=409)

    @router.post("/{identifier}/pull-request")
    def link(identifier: str, payload: dict, request: Request):
        return call(request, lambda: links.link(identifier, payload, request.state.actor))

    @router.get("/{identifier}/pull-request")
    def read(identifier: str, request: Request, project: str = Query(min_length=1, max_length=64),
             workspace: str = Query(min_length=1, max_length=64)):
        return call(request, lambda: links.read(project, workspace, identifier))

    return router
