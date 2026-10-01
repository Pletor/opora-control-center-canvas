"""Rozhraní Editoru: graf plátna, kresby, wireframe kontext a odstraňování."""

from fastapi import APIRouter

from backend.editor.node.wireframe_context import wireframe_context


def create_canvas_router(service):
    router = APIRouter(prefix="/api", tags=["canvas"])

    @router.get("/view")
    def view(project: str = "draft", workspace: str = "draft"):
        return service.view(project, workspace)

    @router.post("/graph")
    def graph(payload: dict):
        # `undo` je krok zpět plátna (Ctrl+Z): snímek smí uzel nebo vazbu vypustit, ale nic nemaže.
        return service.save_graph(
            payload.get("project"),
            payload.get("workspace"),
            payload.get("graph"),
            payload.get("digest"),
            undo=payload.get("undo") is True,
        )

    @router.get("/drawing")
    def drawing(project: str, workspace: str, layer: str = ""):
        return service.drawing(project, workspace, layer)

    @router.post("/drawing")
    def save_drawing(payload: dict):
        return service.drawing(
            payload.get("project"), payload.get("workspace"), payload.get("layer"), payload
        )

    @router.get("/wireframe-context")
    def wireframe_context_api(project: str, workspace: str, layer: str = ""):
        drawing = service.drawing(project, workspace, layer)
        return wireframe_context(project, workspace, layer, drawing)

    @router.get("/removal-preview")
    def removal_preview(project: str, workspace: str, kind: str, target: str):
        return service.removals.preview(project, workspace, kind, target)

    @router.post("/remove")
    def remove_item(payload: dict):
        return service.removals.remove(payload)

    return router
