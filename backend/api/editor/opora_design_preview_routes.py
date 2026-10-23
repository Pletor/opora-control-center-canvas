"""Design náhled karty (docs/design-nahled.md): screenshoty `evidence.preview`, „Potvrdit vzhled“ a režim karty."""
import json
from urllib.parse import urlencode

from fastapi import APIRouter, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response

from backend.api.http_etag import conditional, etag_of, matches
from backend.canvas import opora_design_mode as design_mode
from backend.canvas import opora_design_preview as preview
from backend.canvas.opora_execution_validation import validate
from backend.canvas.opora_review_jobs import ReviewJobService
from backend.project.design import design_system

SCOPE = {"min_length": 1, "max_length": 64}
NODE = {"min_length": 1, "max_length": 80}
# 8 PNG po 2 MiB v base64 (+1/3) a návrh DESIGN.md; strop platí dřív, než se JSON čte.
MAX_BODY = 23 * 1024 * 1024
MAX_SMALL_BODY = 4 * 1024
PNG_CSP = "default-src 'none'; sandbox"


def error(message, code, status, **extra):
    return JSONResponse({"error": message, "code": code, **extra}, status_code=status)


async def bounded_json(request, limit):
    """JSON tělo, nebo (None, odpověď) při překročení stropu či neplatném JSON."""
    declared = request.headers.get("content-length")
    if declared is not None and (not declared.isdigit() or int(declared) > limit):
        return None, error(f"Request body exceeds {limit} bytes.", "payload_too_large", 413)
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            return None, error(f"Request body exceeds {limit} bytes.", "payload_too_large", 413)
        chunks.append(chunk)
    try:
        return json.loads(b"".join(chunks)), None
    except (ValueError, RecursionError):
        return None, error("Request body is not JSON.", "invalid_request", 400)


def identity(request):
    """Člověk (cookie UI) nebo pojmenovaný agent (`X-Opora-Actor`), jako u PR Lens."""
    actor, name = getattr(request.state, "actor", None), getattr(request.state, "agent", None)
    if actor not in ("human", "agent") or (actor == "agent" and (not isinstance(name, str) or not name.strip())):
        return None
    return "agent:" + name if actor == "agent" else "human"


def human_only(request, message):
    """Jen člověk v UI: agent 403, neznámý původce 428 (UI si obnoví doklad), jako `require_human`."""
    actor = getattr(request.state, "actor", None)
    if actor == "human":
        return None
    return error(message, "human_required", 403 if actor == "agent" else 428, humanRequired=True)


def create_design_preview_router(service, jobs=None):
    router = APIRouter(prefix="/api/oporahub", tags=["oporahub"])
    addenda = preview.PreviewAddenda(jobs or ReviewJobService(service))

    @router.post("/review-jobs/preview")
    async def submit(request: Request):
        by = identity(request)
        if by is None:
            return error("Review identity is required.", "identity_required", 428)
        payload, failure = await bounded_json(request, MAX_BODY)
        if failure:
            return failure
        try:
            return await run_in_threadpool(addenda.submit, payload, by)
        except ValueError as exc:
            return error(str(exc), "review_conflict", 409)

    @router.get("/review-preview")
    def read(request: Request, project: str = Query(**SCOPE), workspace: str = Query(**SCOPE),
             nodeId: str = Query(**NODE)):
        if identity(request) is None:
            return error("Review identity is required.", "identity_required", 428)
        try:
            validate({"project": project, "workspace": workspace, "nodeId": nodeId}, {"nodeId"})
        except ValueError as exc:
            return error(str(exc), "invalid_request", 400)
        with service.graph_lock_for(project), service.lock_for(project):
            body = preview.for_node(service.db_for(project), project, workspace, nodeId)
        body["sketchUrl"] = "/api/layout-preview?" + urlencode({"project": project, "workspace": workspace,
                                                                "layer": nodeId})
        body["designSystem"] = design_system.reference(service, project)  # git mimo zámky projektu
        body["designSystemUrl"] = "/api/oporahub/design-system?" + urlencode({"project": project})
        return conditional(request, etag_of("review-preview", project, workspace, nodeId, body), lambda: body)

    @router.get("/review-preview/file")
    def file(request: Request, project: str = Query(**SCOPE), workspace: str = Query(**SCOPE),
             nodeId: str = Query(**NODE), fileId: str = Query(min_length=1, max_length=120)):
        if identity(request) is None:
            return error("Review identity is required.", "identity_required", 428)
        try:
            validate({"project": project, "workspace": workspace, "nodeId": nodeId}, {"nodeId"})
        except ValueError as exc:
            return error(str(exc), "invalid_request", 400)
        tag = etag_of("review-preview-file", project, fileId)  # obsahová adresa: stejné ID = stejné bajty
        headers = {"ETag": tag, "Content-Security-Policy": PNG_CSP}
        if matches(request.headers.get("if-none-match"), tag):
            return Response(status_code=304, headers=headers)
        with service.graph_lock_for(project), service.lock_for(project):
            data = preview.png(service.db_for(project), project, workspace, nodeId, fileId)
        if data is None:
            return error("Screenshot not found for this card.", "not_found", 404)
        return Response(data, media_type="image/png", headers=headers)

    @router.post("/review-preview/confirm")
    async def confirm(request: Request):
        if denied := human_only(request, "Vzhled potvrzuje člověk v UI."):
            return denied
        payload, failure = await bounded_json(request, MAX_SMALL_BODY)
        if failure:
            return failure
        try:
            return await run_in_threadpool(preview.confirm, service, payload, "human")
        except ValueError as exc:
            return error(str(exc), "review_conflict", 409)

    @router.post("/design-mode")
    async def set_mode(request: Request):
        if denied := human_only(request, "Režim design karty mění člověk v UI."):
            return denied
        payload, failure = await bounded_json(request, MAX_SMALL_BODY)
        if failure:
            return failure
        try:
            return await run_in_threadpool(design_mode.set_mode, service, payload, "human")
        except ValueError as exc:
            return error(str(exc), "invalid_request", 409)

    return router
