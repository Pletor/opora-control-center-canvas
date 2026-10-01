"""HTTP DTO pro skutečné Hook řízení; token zůstává pouze v Authorization/client configu."""

from fastapi import APIRouter, Header

from backend.agent_control.hook_control import HookControl


def _bearer(value):
    if not isinstance(value, str) or not value.startswith("Bearer ") or len(value) > 500:
        return None
    return value[7:]


def create_hook_router(service, *, port=8740):
    control = HookControl(service, port=port)
    service.hook_control = control
    router = APIRouter(prefix="/api/agent-hooks", tags=["agent-hooks"])

    @router.get("")
    def list_bindings(project: str, workspace: str, nodeId: str):
        return control.list(project, workspace, nodeId)

    @router.post("/bind")
    def bind(payload: dict):
        return control.bind(payload)

    @router.post("/control")
    def apply_control(payload: dict):
        if not isinstance(payload, dict) or set(payload) != {"bindingId", "expectedRevision", "action", "confirmed"} or payload["confirmed"] is not True:
            raise ValueError("Hook control vyžaduje explicitní potvrzení.")
        return {"binding": control.control(payload["bindingId"], payload["expectedRevision"], payload["action"])}

    @router.get("/events")
    def events(bindingId: str):
        return control.events(bindingId)

    @router.post("/event")
    def hook_event(payload: dict, authorization: str | None = Header(default=None)):
        if not isinstance(payload, dict) or set(payload) != {"bindingId", "event"}:
            return {"continue": False, "stopReason": "Neplatný Hook požadavek; bezpečně zastaveno."}
        return control.event(payload["bindingId"], _bearer(authorization), payload["event"])

    @router.post("/ack")
    def acknowledge(payload: dict, authorization: str | None = Header(default=None)):
        if not isinstance(payload, dict) or set(payload) != {"bindingId", "sessionId", "taskRevision"}:
            raise ValueError("Neplatný ACK požadavek.")
        token = _bearer(authorization)
        if token is None:
            raise ValueError("ACK vyžaduje klientský bearer token.")
        return control.ack(payload["bindingId"], token, payload["sessionId"], payload["taskRevision"])

    return router
