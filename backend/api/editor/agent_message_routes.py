"""HTTP adaptér pro pasivní adresované zprávy mezi kartami editoru."""

from fastapi import APIRouter


def create_agent_message_router(store):
    router = APIRouter(prefix="/api/desktop-v3", tags=["desktop-v3"])

    @router.get("/agent-messages")
    def list_messages(project: str, workspace: str, nodeId: str, direction: str, before: str | None = None):
        return store.list(project, workspace, nodeId, direction, before)

    @router.post("/agent-messages")
    def create_message(payload: dict):
        return {"message": store.create(payload)}

    @router.post("/agent-message-receipt")
    def create_receipt(payload: dict):
        return {"message": store.receipt(payload)}

    return router
