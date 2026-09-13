import os
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api.editor.desktop_v3_routes import create_desktop_v3_router
from backend.api.live_run.agent_routes import create_agent_router
from backend.api.project.archify_routes import create_archify_router
from backend.api.project.graphify_routes import create_graphify_router
from backend.canvas.canvas_service import CanvasService
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.agent_packet.desktop_v3_packets import DesktopV3Packets
from backend.editor.node.node_journal import NodeJournal
from backend.editor.node.node_links import NodeLinks
from backend.editor.node.wireframe_context import wireframe_context
from backend.integrations.build_identity import build_identity
from backend.live_run.node_sessions import create_node_sessions_router
from backend.paths import DIST_DIR
from backend.project.maps.map_refresh import MapRefresh, create_map_refresh_router
from backend.project.workspace.workspace_sources import create_workspace_router


def create_app(data_root=None):
    service = CanvasService(data_root or os.environ.get("OPORA_CANVAS_DATA", ".data/production"))

    desktop_state = DesktopV3State(service)
    service.desktop_v3_state = desktop_state
    desktop_packets = DesktopV3Packets(service, desktop_state)
    links = NodeLinks(service)
    journal = NodeJournal(service)
    identity = build_identity(service.root)
    map_refresh = MapRefresh(service)

    @asynccontextmanager
    async def lifespan(app):
        map_refresh.start()
        yield
        map_refresh.close()
        service.close()

    app = FastAPI(title="Opora Canvas", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.service = service
    app.state.map_refresh = map_refresh
    port = int(os.environ.get("OPORA_CANVAS_PORT", "8740"))
    if not 1 <= port <= 65535:
        raise ValueError("Neplatný lokální port.")

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        host = request.headers.get("host", "")
        if host not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            return JSONResponse({"error": "Nepovolený Host."}, status_code=403)
        origin = request.headers.get("origin")
        if origin and origin != "http://" + host:
            return JSONResponse({"error": "Nepovolený Origin."}, status_code=403)
        if request.method not in ("GET", "HEAD"):
            if (
                origin != "http://" + host
                or request.headers.get("content-type", "").split(";")[0] != "application/json"
            ):
                return JSONResponse(
                    {"error": "Zápisy vyžadují stejný Origin a JSON."}, status_code=403
                )
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 2000000:
                    return JSONResponse({"error": "Požadavek je příliš velký."}, status_code=413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"error": str(exc)}, status_code=409)

    @app.exception_handler(sqlite3.Error)
    async def storage_error(request, exc):
        return JSONResponse(
            {
                "error": "Úložiště není dostupné; uložení nebylo potvrzeno. Rozepsaný text zachovejte."
            },
            status_code=503,
        )

    @app.exception_handler(OSError)
    async def unavailable(request, exc):
        return JSONResponse(
            {"error": "Zdroj není dostupný; soubory nebyly přepsány."}, status_code=503
        )

    @app.get("/api/health")
    def health():
        return {"status": "ok", "product": "Opora Canvas", "execution": "explicit_bounded"}

    @app.get("/api/build-identity")
    def runtime_identity():
        return identity

    @app.get("/api/bootstrap")
    def bootstrap():
        return service.bootstrap()

    @app.get("/api/project-settings")
    def project_settings(project: str):
        return service.project_hub.settings(project)

    @app.post("/api/project-settings")
    def save_project_settings(payload: dict):
        return service.project_hub.save_settings(payload)

    @app.post("/api/local-project")
    def local_project(payload: dict):
        return service.project_hub.local_project(payload)

    @app.post("/api/empty-project")
    def empty_project(payload: dict):
        return service.project_hub.empty_project(payload)

    @app.get("/api/view")
    def view(project: str = "draft", workspace: str = "draft"):
        return service.view(project, workspace)

    @app.get("/api/drawing")
    def drawing(project: str, workspace: str, layer: str = ""):
        return service.drawing(project, workspace, layer)

    @app.post("/api/drawing")
    def save_drawing(payload: dict):
        return service.drawing(
            payload.get("project"), payload.get("workspace"), payload.get("layer"), payload
        )

    @app.get("/api/wireframe-context")
    def wireframe_context_api(project: str, workspace: str, layer: str = ""):
        drawing = service.drawing(project, workspace, layer)
        return wireframe_context(project, workspace, layer, drawing)

    @app.post("/api/graph")
    def graph(payload: dict):
        return service.save_graph(
            payload.get("project"),
            payload.get("workspace"),
            payload.get("graph"),
            payload.get("digest"),
        )

    @app.get("/api/node-text")
    def node_text(project: str, workspace: str, node: str):
        return service.texts.access(project, workspace, node)

    @app.post("/api/node-text")
    def save_node_text(payload: dict):
        return service.texts.access(payload.get("project"), payload.get("workspace"), payload.get("node"), payload)

    @app.get("/api/node-links")
    def node_links(project: str, workspace: str, node: str):
        return links.links(project, workspace, node)

    @app.get("/api/node-journal")
    def node_journal(project: str, workspace: str, node: str, day: str):
        return journal.access(project, workspace, node, day)

    @app.post("/api/node-journal")
    def save_node_journal(payload: dict):
        return journal.access(
            payload.get("project"), payload.get("workspace"), payload.get("node"), payload.get("day"), payload
        )

    @app.get("/api/node-spec")
    def node_spec(project: str, workspace: str, node: str):
        return service.node_spec(project, workspace, node)

    @app.get("/api/node-spec/history")
    def node_spec_history(project: str, workspace: str, node: str):
        return service.node_spec(project, workspace, node, history=True)

    @app.post("/api/node-spec")
    def save_node_spec(payload: dict):
        return service.node_spec(
            payload.get("project"), payload.get("workspace"), payload.get("node"), payload
        )

    @app.get("/api/removal-preview")
    def removal_preview(project: str, workspace: str, kind: str, target: str):
        return service.removals.preview(project, workspace, kind, target)

    @app.post("/api/remove")
    def remove_item(payload: dict):
        return service.removals.remove(payload)

    @app.get("/api/project-workspaces")
    def project_workspaces(project: str):
        item = service.project_hub.settings(project)["project"]
        if item["sourceKind"] != "git":
            return {"workspaces": [{"id": "draft", "label": "Lokální pracovní návrh"}]}
        return {"workspaces": [{"id": "main", "label": "Schválená větev · pouze čtení"}] + [{"id": w["id"], "label": w["actor"] + " · " + w["branch"]} for w in service.workspaces(project)]}

    @app.post("/api/connect")
    def connect(payload: dict):
        return service.connect(payload.get("url"), payload.get("approved"))

    @app.post("/api/workspaces")
    def workspace(payload: dict):
        return service.create_workspace(
            payload.get("project"), payload.get("nodeId"), payload.get("actor")
        )

    @app.post("/api/sync")
    def sync(payload: dict):
        if payload.get("confirmed") is not True:
            raise ValueError("Potvrďte aktualizaci spravovaného mainu.")
        return service.sync(payload.get("project"))

    app.include_router(create_agent_router(service))
    app.include_router(create_node_sessions_router(service))
    app.include_router(create_archify_router(service))
    app.include_router(create_graphify_router(service))
    app.include_router(create_map_refresh_router(map_refresh))
    app.include_router(create_workspace_router(service))
    app.include_router(create_desktop_v3_router(desktop_state, desktop_packets))
    dist = DIST_DIR
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="canvas")
    return app
