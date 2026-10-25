"""Folder project -> GitHub repository binding; only a middleware-verified human session may change it."""
from fastapi import APIRouter, Query, Request

from backend.canvas import opora_folder_repository as binding
from backend.canvas.activity_log import require_human


def create_folder_repository_router(service):
    router = APIRouter(prefix="/api/oporahub/repository", tags=["oporahub"])

    def human(request):
        require_human(request.state.actor, "Připojení repozitáře projektu patří člověku v UI.")
        return {"kind": "human", "name": "Člověk"}

    @router.get("")
    def current(request: Request, project: str = Query(min_length=1, max_length=64)):
        return binding.status(service, project, request.state.actor)

    @router.post("")
    def bind(payload: dict, request: Request):
        return binding.bind(service, payload, human(request))

    @router.post("/unbind")
    def unbind(payload: dict, request: Request):
        return binding.unbind(service, payload, human(request))

    return router
