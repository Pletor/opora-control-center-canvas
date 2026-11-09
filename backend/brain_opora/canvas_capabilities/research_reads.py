"""Lossless research reads delegate to the existing immutable revision services."""
from backend.editor.research import service as research, reads, events
from backend.brain_opora.canvas_capabilities.contracts import contract

CONTRACTS = {
    "research_routes.listing": contract(optional=("archived",), types={"archived": "boolean"}),
    "research_routes.detail": contract(("id",), ("revision",), types={"revision": "integer"}),
    "research_routes.edge_detail": contract(("id",), ("revision",), types={"revision": "integer"}),
    "research_read_routes.topics": contract(optional=("archived",), types={"archived": "boolean"}),
    "research_read_routes.parts": contract(("id",), ("revision", "offset", "size", "snapshot"),
        types={"revision": "integer", "offset": "integer", "size": "integer"}),
    "research_read_routes.changes": contract(optional=("after", "limit"), types={"after": "integer", "limit": "integer"}),
}


def read(service, project, workspace, capability, data):
    if capability == "research_routes.listing":
        return {**research.listing(service, project, workspace, data.get("archived", False)), "workspace": workspace}
    if capability == "research_routes.detail":
        return {**research.detail(service, project, workspace, data["id"], data.get("revision")), "workspace": workspace}
    if capability == "research_routes.edge_detail":
        return {**research.edge_detail(service, project, workspace, data["id"], data.get("revision")), "workspace": workspace}
    if capability == "research_read_routes.topics":
        return reads.topics(service, project, workspace, data.get("archived", False))
    if capability == "research_read_routes.parts":
        return reads.parts(service, project, workspace, data["id"], data.get("revision"),
                           data.get("offset", 0), data.get("size", 12000), data.get("snapshot"))
    if capability == "research_read_routes.changes":
        return events.listing(service, project, workspace, data.get("after", 0), data.get("limit", 100))
    raise RuntimeError("Unknown research adapter")
