"""Browser-owned navigation attachment: agent tokens never authorize pairing or UI acknowledgements."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.brain_opora.canvas_capabilities import view_attachments
from backend.canvas.payload_errors import InvalidPayload


def create_canvas_view_attachment_router(service):
    router = APIRouter(prefix="/api/canvas-view-attachments", tags=["canvas-view"])

    def human(request):
        return request.state.actor == "human"

    def forbidden():
        return JSONResponse({"error": "Only the human browser can attach or acknowledge its view."}, status_code=403)

    @router.get("/sessions")
    def sessions(request: Request, project: str, workspace: str):
        if not human(request):
            return forbidden()
        return view_attachments.sessions(service, project, workspace)

    @router.post("/{action}")
    def apply(action: str, payload: dict, request: Request):
        if not human(request):
            return forbidden()
        if action not in {"attach", "poll", "ack", "pending", "detach"}:
            raise InvalidPayload("Unknown attachment action.")
        required = {"project", "workspace", "sessionId"}
        if action != "attach":
            required |= {"attachmentId", "secret"}
        if action == "ack":
            required |= {"revision", "view", "renderEpoch"}
        if set(payload) != required:
            raise InvalidPayload("Invalid browser attachment fields.")
        if action == "attach":
            return view_attachments.attach(service, payload["project"], payload["workspace"], payload["sessionId"])
        return view_attachments.act(service, payload["project"], payload["workspace"], payload, action)

    return router
