"""Finite scoped Canvas capabilities for authenticated Heart sessions."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.brain_opora.canvas_capabilities import access, catalog
from backend.brain_opora.canvas_capabilities.invoke import invoke
from backend.canvas.payload_errors import InvalidPayload


def create_canvas_capabilities_router(service):
    router = APIRouter(prefix="/api/brain/canvas", tags=["heart-canvas"])

    def run(request, project, workspace, callback):
        try:
            session = access.authenticate(service, request, project, workspace)
            return callback(session)
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)

    @router.get("/capabilities")
    def discover(request: Request, project: str, workspace: str):
        return run(request, project, workspace, lambda _: catalog.discover())

    @router.get("/capabilities/{operation_id}")
    def describe(operation_id: str, request: Request, project: str, workspace: str):
        return run(request, project, workspace, lambda _: catalog.describe(operation_id))

    @router.post("/invoke")
    def execute(payload: dict, request: Request):
        if (payload.get('capability') != 'site_admin_routes.proposal_create'
                and getattr(request.state, 'received_body_bytes', 0) > 14_500_000):
            return JSONResponse({'error': 'Capability request exceeds 14500000 bytes.', 'code': 'body_too_large'}, status_code=413)
        required = {"project", "workspace", "capability", "input"}
        if required - payload.keys() or payload.keys() - required - {"requestId"}:
            raise InvalidPayload("Expected scoped capability, input and optional requestId.")
        return run(request, payload["project"], payload["workspace"], lambda session: invoke(
            service, payload["project"], payload["workspace"], session, payload["capability"],
            payload["input"], payload.get("requestId")))

    return router
