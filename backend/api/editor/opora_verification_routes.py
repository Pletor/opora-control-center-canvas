"""Bounded formal evidence imports and inert downloads, with execution fencing."""
import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from backend.canvas.opora_verifications import OporaVerifications

BODY_LIMIT = 12 * 1024 * 1024


def create_opora_verification_router(service):
    router = APIRouter(prefix="/api/oporahub/verifications", tags=["oporahub"])
    verifications = OporaVerifications(service)

    def call(request, action):
        if request.state.actor not in ("human", "agent"):
            return JSONResponse({"error": "Execution identity is required.", "code": "identity_required"}, status_code=428)
        try:
            return action()
        except (ValueError, RecursionError, UnicodeError) as exc:
            return JSONResponse({"error": str(exc), "code": "verification_conflict"}, status_code=409)

    async def write(request, action):
        if request.state.actor not in ("human", "agent"):
            return call(request, lambda: None)
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > BODY_LIMIT:
                return JSONResponse({"error": "Verification body exceeds 12 MiB."}, status_code=413)
            body.extend(chunk)
        def invoke():
            def finite(value):
                raise ValueError("Verification JSON must be finite.")
            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError("Duplicate verification JSON field.")
                    result[key] = value
                return result
            payload = json.loads(body, parse_constant=finite, object_pairs_hook=unique)
            return action(payload)
        return await run_in_threadpool(call, request, invoke)

    @router.post("/requests")
    async def create(request: Request):
        return await write(request, verifications.create)

    @router.post("/{identifier}/report")
    async def report(identifier: str, request: Request):
        return await write(request, lambda payload: verifications.submit_report(identifier, payload))

    @router.get("")
    def history(project: str, workspace: str, request: Request, nodeId: str | None = None):
        return call(request, lambda: verifications.history(project, workspace, nodeId))

    @router.get("/{identifier}")
    def detail(identifier: str, project: str, workspace: str, request: Request):
        return call(request, lambda: verifications.read(identifier, project, workspace))

    @router.get("/{identifier}/artifacts/{fingerprint}")
    def artifact(identifier: str, fingerprint: str, project: str, workspace: str, request: Request):
        def download():
            data = verifications.artifact(identifier, fingerprint, project, workspace)
            return Response(data, media_type="application/octet-stream", headers={
                "Content-Disposition": 'attachment; filename="' + fingerprint + '.bin"',
                "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox; default-src 'none'"})
        return call(request, download)

    return router
