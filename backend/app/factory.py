import os
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api.app_routes import create_app_router
from backend.api.editor.canvas_routes import create_canvas_router
from backend.api.editor.desktop_v3_routes import create_desktop_v3_router
from backend.api.editor.node_routes import create_node_router
from backend.api.live_run.agent_routes import create_agent_router
from backend.api.live_run.node_session_routes import create_node_sessions_router
from backend.api.project.archify_routes import create_archify_router
from backend.api.project.graphify_routes import create_graphify_router
from backend.api.project.map_refresh_routes import create_map_refresh_router
from backend.api.project.project_workspace_routes import create_project_workspace_router
from backend.api.project.workspace_routes import create_workspace_router
from backend.api.project_setup.project_routes import create_project_setup_router
from backend.canvas.canvas_service import CanvasService
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.agent_packet.desktop_v3_packets import DesktopV3Packets
from backend.integrations.build_identity import build_identity
from backend.paths import DIST_DIR
from backend.project.maps.map_refresh import MapRefresh


def create_app(data_root=None):
    service = CanvasService(data_root or os.environ.get("OPORA_CANVAS_DATA", ".data/production"))

    desktop_state = DesktopV3State(service)
    service.desktop_v3_state = desktop_state
    desktop_packets = DesktopV3Packets(service, desktop_state)
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

    # aplikace
    app.include_router(create_app_router(service, identity))
    # krok 1: nastavení projektu
    app.include_router(create_project_setup_router(service))
    # prostředí Projekt
    app.include_router(create_project_workspace_router(service))
    app.include_router(create_workspace_router(service))
    app.include_router(create_archify_router(service))
    app.include_router(create_graphify_router(service))
    app.include_router(create_map_refresh_router(map_refresh))
    # prostředí Editor
    app.include_router(create_canvas_router(service))
    app.include_router(create_node_router(service))
    app.include_router(create_desktop_v3_router(desktop_state, desktop_packets))
    # prostředí Live Run
    app.include_router(create_agent_router(service))
    app.include_router(create_node_sessions_router(service))

    dist = DIST_DIR
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="canvas")
    return app
