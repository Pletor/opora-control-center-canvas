"""Scoped immutable content review API; agents propose, humans accept."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.canvas.opora_content_acceptance import OporaContentAcceptance
from backend.canvas.opora_content_changes import OporaContentChanges

CONTENT_BODY_LIMIT = 12 * 1024 * 1024


def create_opora_content_router(canvas):
    router = APIRouter(prefix="/api/oporahub/content-changes", tags=["oporahub"])
    changes, acceptance = OporaContentChanges(canvas), OporaContentAcceptance(canvas)

    def call(request, action):
        actor = request.state.actor
        if actor not in {"human", "agent"}:
            return JSONResponse({"error": "Content review identity is required.", "code": "identity_required"}, status_code=428)
        try:
            by = {"kind": actor, "name": request.state.agent if actor == "agent" else "Human"}
            return action(by)
        except (ValueError, TypeError) as error:
            return JSONResponse({"error": str(error), "code": "content_conflict"}, status_code=409)

    @router.get("")
    def listing(project: str, workspace: str, request: Request):
        def read(by):
            value = changes.list(project, workspace)
            return {**value, "canAccept": by["kind"] == "human" and not value["readOnly"]}
        return call(request, read)

    @router.get("/{identifier}")
    def detail(identifier: str, project: str, workspace: str, request: Request):
        def read(by):
            value = changes.read(project, workspace, identifier)
            return {**value, "canAccept": by["kind"] == "human" and not value["readOnly"] and value["accepted"] is None}
        return call(request, read)

    @router.post("")
    def create(payload: dict, request: Request):
        return call(request, lambda by: changes.create(payload, by))

    @router.post("/{identifier}/rebase")
    def rebase(identifier: str, payload: dict, request: Request):
        return call(request, lambda by: changes.rebase(identifier, payload, by))

    @router.post("/{identifier}/accept")
    def accept(identifier: str, payload: dict, request: Request):
        return call(request, lambda by: acceptance.accept(identifier, payload, by))

    return router
