"""API knihovny pláten toku (`backend/flow/library.py`, kontrakt `docs/navrhy/2026-11-04-knihovna-platna-toku.md` §3).

Tenký router nad registry.sqlite pod `registry_lock`. Kdo píše (`writer_refusal`): do části `human` jen člověk v UI
(`require_human`, jinak 403/428), do části `agent` člověk nebo relace brány (`X-Opora-Gate-Token`, role `worker` /
`heart`, jinak 401 `gate_token_invalid`). Povýšení do knihovny člověka (`promote`) jen člověk. Převzetí do projektu
(`adopt`) píše do projektu, proto jde přes zeď brány projektu jako ostatní zápisy toků. Verze a graf plátna se mění
přes `/api/flow/workflows/{id}/versions` (zeď tam hlídá stejná pravidla knihovny). 409 nese `{error, code}`.
"""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.brain_opora.determinism import gate, tokens, wall
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.canvas.activity_log import require_human
from backend.flow import library
from backend.flow.graph_check import FlowInvalid
from backend.flow.workflows import FlowConflict, FlowNotFound

Part = Query(default="human", pattern="^(human|agent)$")


class FolderIn(BaseModel):
    owner: str = Field(pattern="^(human|agent)$")
    slug: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    order: int | None = None


class FolderPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    order: int | None = None


class FlowIn(BaseModel):
    folder: str = Field(min_length=1, max_length=64)
    slug: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class AdoptIn(BaseModel):
    project: str = Field(min_length=1, max_length=64)
    nodeId: str | None = Field(default=None, min_length=1, max_length=200, pattern=r"^\S+$")


class PromoteIn(BaseModel):
    folder: str | None = Field(default=None, max_length=64)


def writer_refusal(service, request, part):
    """Smí požadavek psát do části knihovny? `None` = ano, jinak odpověď 401/403 (člověk: výjimka `HumanRequired`)."""
    actor = getattr(request.state, "actor", None)
    if part == "human":
        require_human(actor, "Do knihovny člověka píše jen člověk v UI.")
    elif actor != "human":
        try:
            gate.authenticate(service, request.headers.get(tokens.HEADER), None, ("worker", "heart"))
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)
    return None


def create_library_router(service):
    router = APIRouter(prefix="/api/library", tags=["library"])
    with service.registry_lock:
        library.seed_folders(service.db)

    def call(action, *args):
        try:
            with service.registry_lock:
                return action(service.db, *args)
        except FlowNotFound as error:
            raise HTTPException(404, str(error)) from error
        except FlowConflict as error:
            if error.code:
                return JSONResponse({"error": str(error), "code": error.code}, status_code=409)
            raise HTTPException(409, str(error)) from error
        except FlowInvalid as error:
            raise HTTPException(422, str(error)) from error

    def guarded(request, part, action, *args):
        refused = writer_refusal(service, request, part)
        return refused or call(action, *args)

    def folder_part(folder_id):
        return call(library.get_folder, folder_id)["owner"]

    @router.get("")
    def library_list(owner: str = Part):
        return {"owner": owner, "folders": call(library.list_library, owner)}

    @router.post("/folders")
    def folder_create(body: FolderIn, request: Request):
        return guarded(request, body.owner, library.create_folder, body.owner, body.slug, body.title,
                       body.description, body.order)

    @router.patch("/folders/{folder_id}")
    def folder_update(folder_id: str, body: FolderPatch, request: Request):
        return guarded(request, folder_part(folder_id), library.update_folder, folder_id, body.title,
                       body.description, body.order)

    @router.delete("/folders/{folder_id}")
    def folder_delete(folder_id: str, request: Request):
        return guarded(request, folder_part(folder_id), library.delete_folder, folder_id)

    @router.post("/flows")
    def flow_create(body: FlowIn, request: Request):
        return guarded(request, folder_part(body.folder), library.create_flow, body.folder, body.slug, body.title,
                       body.description)

    @router.get("/flows/{workflow_id}")
    def flow_detail(workflow_id: str):
        return call(library.flow_detail, workflow_id)

    @router.post("/flows/{workflow_id}/adopt")
    def flow_adopt(workflow_id: str, body: AdoptIn, request: Request):
        verdict = wall.check(service, request.method, request.url.path, getattr(request.state, "actor", None),
                             request.headers.get(tokens.HEADER), body.project, lambda: "")
        if not verdict.allow:
            return JSONResponse(verdict.body(), status_code=verdict.status)
        return call(library.adopt, workflow_id, body.project, body.nodeId)

    @router.post("/flows/{workflow_id}/contribute")
    def flow_contribute(workflow_id: str, body: FlowIn, request: Request):
        return guarded(request, folder_part(body.folder), library.contribute, workflow_id, body.folder, body.slug,
                       body.title)

    @router.post("/flows/{workflow_id}/promote")
    def flow_promote(workflow_id: str, request: Request, body: PromoteIn | None = None):
        require_human(getattr(request.state, "actor", None), "Do knihovny člověka povyšuje jen člověk v UI.")
        return call(library.promote, workflow_id, body.folder if body else None)

    return router
