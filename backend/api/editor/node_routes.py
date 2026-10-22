"""Rozhraní Editoru: obsah jednoho uzlu – text, odkazy, deník, zadání a nahrané podklady."""

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from backend.canvas.opora_step_results import plan_view
from backend.editor.node.node_journal import NodeJournal
from backend.editor.node.node_links import NodeLinks
from backend.editor.node.node_materials import NodeMaterials


def create_node_router(service):
    router = APIRouter(prefix="/api", tags=["node"])
    links = NodeLinks(service)
    journal = NodeJournal(service)
    materials = NodeMaterials(service)

    @router.get("/node-text")
    def node_text(project: str, workspace: str, node: str):
        return service.texts.access(project, workspace, node)

    @router.post("/node-text")
    def save_node_text(payload: dict):
        return service.texts.access(payload.get("project"), payload.get("workspace"), payload.get("node"), payload)

    @router.get("/node-links")
    def node_links(project: str, workspace: str, node: str):
        return links.links(project, workspace, node)

    @router.get("/node-journal")
    def node_journal(project: str, workspace: str, node: str, day: str):
        return journal.access(project, workspace, node, day)

    @router.post("/node-journal")
    def save_node_journal(payload: dict):
        return journal.access(
            payload.get("project"), payload.get("workspace"), payload.get("node"), payload.get("day"), payload
        )

    def with_plan(project, workspace, node, result):
        # Working vs accepted plan steps (docs/oporahub-plan-steps.md); read-only main has none.
        return plan_view(service, project, workspace, node, result) if result.get("available") else result

    @router.get("/node-spec")
    def node_spec(project: str, workspace: str, node: str):
        return with_plan(project, workspace, node, service.node_spec(project, workspace, node))

    @router.get("/node-spec/history")
    def node_spec_history(project: str, workspace: str, node: str):
        return service.node_spec(project, workspace, node, history=True)

    @router.post("/node-spec")
    def save_node_spec(payload: dict):
        result = service.node_spec(payload.get("project"), payload.get("workspace"), payload.get("node"), payload)
        return with_plan(payload["project"], payload["workspace"], payload["node"], result)

    @router.post("/node-materials/upload")
    def upload_material(payload: dict):
        """Obrázek jako data URL (JSON); uloží se do složky projektu, odkaz si klient zapíše do stavu uzlu."""
        return materials.save_upload(payload)

    @router.get("/node-materials/file")
    def material_file(project: str, nodeId: str, file: str):
        try:
            target, mime = materials.file_path(project, nodeId, file)
        except FileNotFoundError:
            return JSONResponse({"error": "Podklad není uložen."}, status_code=404)
        return FileResponse(target, media_type=mime, headers={"Cache-Control": "no-store"})

    @router.post("/node-materials/remove")
    def remove_material(payload: dict):
        removed = materials.remove(payload.get("project"), payload.get("nodeId"), payload.get("file"))
        return {"removed": removed}

    return router
