import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .service import CanvasService


def create_app(data_root=None):
    service = CanvasService(data_root or os.environ.get("OPORA_CANVAS_DATA", ".data/production"))

    @asynccontextmanager
    async def lifespan(app):
        yield
        service.close()

    app = FastAPI(title="Opora Canvas", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.service = service
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
        return {"status": "ok", "product": "Opora Canvas", "execution": "disabled"}

    @app.get("/api/bootstrap")
    def bootstrap():
        return service.bootstrap()

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

    @app.post("/api/graph")
    def graph(payload: dict):
        return service.save_graph(
            payload.get("project"),
            payload.get("workspace"),
            payload.get("graph"),
            payload.get("digest"),
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

    dist = Path(__file__).resolve().parent.parent / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="canvas")
    return app
