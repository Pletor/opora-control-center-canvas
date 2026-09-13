"""Rozhraní Editoru: obsah jednoho uzlu – text, odkazy, deník a zadání."""

from fastapi import APIRouter

from backend.editor.node.node_journal import NodeJournal
from backend.editor.node.node_links import NodeLinks


def create_node_router(service):
    router = APIRouter(prefix="/api", tags=["node"])
    links = NodeLinks(service)
    journal = NodeJournal(service)

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

    @router.get("/node-spec")
    def node_spec(project: str, workspace: str, node: str):
        return service.node_spec(project, workspace, node)

    @router.get("/node-spec/history")
    def node_spec_history(project: str, workspace: str, node: str):
        return service.node_spec(project, workspace, node, history=True)

    @router.post("/node-spec")
    def save_node_spec(payload: dict):
        return service.node_spec(
            payload.get("project"), payload.get("workspace"), payload.get("node"), payload
        )

    return router
