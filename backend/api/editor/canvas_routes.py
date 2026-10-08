"""Rozhraní Editoru: graf plátna, dávka plánu, index karet, kresby, wireframe kontext a odstraňování."""

from fastapi import APIRouter, Request
from fastapi.responses import Response

from backend.canvas.canvas_index import DEFAULT_LIMIT, build_index, search
from backend.canvas.canvas_layout import apply_layout, layout_preview
from backend.canvas.canvas_plan import apply_plan
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.node.wireframe_context import wireframe_context


def create_canvas_router(service):
    router = APIRouter(prefix="/api", tags=["canvas"])

    @router.get("/view")
    def view(project: str = "draft", workspace: str = "draft"):
        return service.view(project, workspace)

    @router.post("/canvas-layout")
    def canvas_layout(payload: dict, request: Request):
        return apply_layout(service, payload, actor=request.state.actor)

    @router.get("/layout-preview")
    def preview_layout(project: str, workspace: str, layer: str = ""):
        svg = layout_preview(service.view(project, workspace)["graph"], layer)
        return Response(svg, media_type="image/svg+xml", headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox"})

    @router.get("/canvas-index")
    def canvas_index(project: str = "draft", workspace: str = "draft", q: str = "", limit: int = DEFAULT_LIMIT):
        # Jednotný index karet a vazeb (docs/kontext-karet-a-index.md §5): staví se v paměti,
        # nic neukládá. Graf i stav plochy se čtou pod jedním zámkem grafu, stejně jako `/view`.
        with service.graph_lock:
            graph = service.view(project, workspace)["graph"]
            store = getattr(service, "desktop_v3_state", None) or DesktopV3State(service)
            state = store.read(project, workspace)["state"]
        return search(build_index(graph, state), q, limit)

    @router.post("/graph")
    def graph(payload: dict, request: Request):
        # `undo` je krok zpět plátna (Ctrl+Z): snímek smí uzel nebo vazbu vypustit, ale nic nemaže.
        return service.save_graph(
            payload.get("project"),
            payload.get("workspace"),
            payload.get("graph"),
            payload.get("digest"),
            undo=payload.get("undo") is True,
            actor=request.state.actor,
        )

    @router.post("/canvas-plan")
    def canvas_plan(payload: dict, request: Request):
        # Dávka plánu (docs/davka-planu.md §3): jen přidává, atomicky; `dryRun` nic nezapíše.
        return apply_plan(service, payload, actor=request.state.actor)

    @router.get("/drawing")
    def drawing(project: str, workspace: str, layer: str = ""):
        return service.drawing(project, workspace, layer)

    @router.post("/drawing")
    def save_drawing(payload: dict):
        return service.drawing(
            payload.get("project"), payload.get("workspace"), payload.get("layer"), payload
        )

    @router.post("/drawing-file")
    def save_drawing_file(payload: dict):
        return service.drawing_file(payload)

    @router.get("/drawing-files")
    def drawing_files(project: str, workspace: str, ids: str = ""):
        return service.drawing_file_list(project, workspace, ids)

    @router.get("/wireframe-context")
    def wireframe_context_api(project: str, workspace: str, layer: str = ""):
        drawing = service.drawing(project, workspace, layer)
        return wireframe_context(project, workspace, layer, drawing)

    @router.get("/removal-preview")
    def removal_preview(project: str, workspace: str, kind: str, target: str):
        return service.removals.preview(project, workspace, kind, target)

    @router.post("/remove")
    def remove_item(payload: dict, request: Request):
        return service.removals.remove(payload, actor=request.state.actor)

    @router.post("/remove/restore")
    def restore_removed(payload: dict):
        # Krok zpět po smazání (docs/hromadne-mazani.md): jednorázový záznam obnovy z `/remove`.
        return service.removals.restore(payload)

    return router
