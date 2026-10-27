"""Rozhraní Studia: technický model domény (`docs/studio.md` §4). `GET` vrací model (prázdný s `revision: 0`, když
ho nikdo neuložil), `PUT` ho uloží nad revizí, ze které vychází. Stejný Origin a JSON zápisu hlídá middleware
aplikace (`backend/app/factory.py`). Model nikdy nesahá na `/api/graph`."""

import json

from fastapi import APIRouter, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool

from backend.canvas.canvas_service import ProjectNotFound
from backend.project.studio.studio_model import (
    BODY_LIMIT,
    StudioModelConflict,
    StudioModelInvalid,
    read_model,
    write_model,
)


def _model_errors(action):
    """404 neznámý projekt, 409 jiná revize, 422 tvar modelu nebo neexistující `binding.nodeId`."""
    try:
        return action()
    except ProjectNotFound as error:
        raise HTTPException(404, str(error)) from error
    except StudioModelInvalid as error:
        raise HTTPException(422, str(error)) from error
    except StudioModelConflict as error:
        raise HTTPException(409, str(error)) from error


def create_studio_model_router(service):
    router = APIRouter(prefix="/api/studio", tags=["studio"])

    @router.get("/model")
    def model_view(project: str = Query(min_length=1, max_length=64), domain: str = Query(min_length=1, max_length=128)):
        return _model_errors(lambda: read_model(service, project, domain))

    @router.put("/model")
    async def model_save(request: Request, project: str = Query(min_length=1, max_length=64),
                         domain: str = Query(min_length=1, max_length=128)):
        raw = await request.body()
        if len(raw) > BODY_LIMIT:
            raise HTTPException(413, "Model je větší než 1 MiB.")
        try:
            body = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise HTTPException(422, "Model není platný JSON.") from error
        # Zápis do SQLite pod zámkem projektu neběží ve smyčce událostí.
        return await run_in_threadpool(_model_errors, lambda: write_model(service, project, domain, body))

    return router
