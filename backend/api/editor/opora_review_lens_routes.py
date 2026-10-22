"""PR Lens review evidence (docs/oporahub-review-jobs.md, "Diagram PR Lens"): optional, never blocking."""
import json

from fastapi import APIRouter, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from backend.canvas import opora_review_lens as review_lens
from backend.canvas.opora_execution_validation import validate
from backend.canvas.opora_review_jobs import ReviewJobService

SCOPE = {"min_length": 1, "max_length": 64}
MAX_BODY = 64 * 1024  # raw request bytes, enforced before any JSON parsing


def error(message, code, status):
    return JSONResponse({"error": message, "code": code}, status_code=status)


async def bounded_body(request):
    """The request body, or None once it exceeds MAX_BODY (declared length first, then streamed bytes)."""
    declared = request.headers.get("content-length")
    if declared is not None and (not declared.isdigit() or int(declared) > MAX_BODY):
        return None
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_BODY:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


def create_review_lens_router(service, jobs=None):
    router = APIRouter(prefix="/api/oporahub", tags=["oporahub"])
    addenda = review_lens.LensAddenda(jobs or ReviewJobService(service))

    def identity(request):
        actor, name = request.state.actor, getattr(request.state, "agent", None)
        if actor not in ("human", "agent") or (actor == "agent" and (not isinstance(name, str) or not name.strip())):
            return None
        return "agent:" + name if actor == "agent" else "human"

    @router.post("/review-jobs/lens")
    async def submit(request: Request):
        by = identity(request)
        if by is None:
            return error("Review identity is required.", "identity_required", 428)
        raw = await bounded_body(request)
        if raw is None:
            return error(f"Lens request body exceeds {MAX_BODY} bytes.", "payload_too_large", 413)
        try:
            payload = json.loads(raw)
        except (ValueError, RecursionError):
            return error("Lens request body is not JSON.", "invalid_request", 400)
        try:
            return await run_in_threadpool(addenda.submit, payload, by)
        except ValueError as exc:
            return error(str(exc), "review_conflict", 409)

    @router.get("/review-lens")
    def read(request: Request, project: str = Query(**SCOPE), workspace: str = Query(**SCOPE),
             nodeId: str = Query(min_length=1, max_length=80)):
        if identity(request) is None:
            return error("Review identity is required.", "identity_required", 428)
        try:
            validate({"project": project, "workspace": workspace, "nodeId": nodeId}, {"nodeId"})
        except ValueError as exc:
            return error(str(exc), "invalid_request", 400)
        with service.graph_lock_for(project), service.lock_for(project):
            return review_lens.for_node(service.db_for(project), project, workspace, nodeId)

    return router
