"""One read-only agent-state document with ETag/If-None-Match (docs/oporahub-agent-state.md)."""
from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse

from backend.api.http_etag import etag_of, matches
from backend.canvas.opora_agent_state import AgentState


def create_opora_agent_state_router(canvas, state=None):
    router = APIRouter(prefix="/api/oporahub", tags=["oporahub"])
    reader = state or AgentState(canvas)

    @router.get("/agent-state")
    def read(project: str, workspace: str, request: Request, cardsOffset: int = Query(0, ge=0)):
        try:
            body = reader.read(project, workspace, cardsOffset)  # cards[] page; actions always whole
        except ValueError as error:
            return JSONResponse({"error": str(error), "code": "agent_state_unavailable"}, status_code=409)
        tag = etag_of({key: value for key, value in body.items() if key != "generatedAt"})
        if matches(request.headers.get("if-none-match"), tag):
            return Response(status_code=304, headers={"ETag": tag})
        return JSONResponse(body, headers={"ETag": tag})

    return router
