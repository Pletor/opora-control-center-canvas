import os
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.routing import Match

from backend.api.access_routes import create_access_router
from backend.api.app_routes import create_app_router
from backend.api.editor.agent_message_routes import create_agent_message_router
from backend.api.editor.assistant_routes import create_assistant_router
from backend.api.editor.canvas_routes import create_canvas_router
from backend.api.editor.claude_code_routes import create_claude_code_router
from backend.api.editor.code_intelligence_routes import create_code_intelligence_router
from backend.api.editor.desktop_v3_routes import create_desktop_v3_router
from backend.api.editor.memory_routes import create_memory_router
from backend.api.editor.node_routes import create_node_router
from backend.api.editor.oporahub_routes import create_oporahub_router
from backend.api.editor.process_routes import create_process_router
from backend.api.editor.rlm_routes import create_rlm_router
from backend.api.editor.semantic_routes import create_semantic_router
from backend.api.editor.sync_routes import create_sync_router
from backend.api.live_run.agent_routes import create_agent_router
from backend.api.live_run.hook_install_routes import create_hook_install_router
from backend.api.live_run.hook_routes import create_hook_router
from backend.api.live_run.node_session_routes import create_node_sessions_router
from backend.api.project.archify_routes import create_archify_router
from backend.api.project.graphify_routes import create_graphify_router
from backend.api.project.map_refresh_routes import create_map_refresh_router
from backend.api.project.project_workspace_routes import create_project_workspace_router
from backend.api.project.workspace_routes import create_workspace_router
from backend.api.project_setup.project_routes import create_project_setup_router
from backend.app.remote_access import (
    COOKIE_NAME,
    TOKEN_REQUIRED,
    RemoteAccess,
    is_loopback_only,
    requires_token,
)
from backend.canvas.canvas_service import CanvasService
from backend.claude_code.assistant.manager import AssistantManager
from backend.claude_code.assistant.router import route as route_message
from backend.claude_code.assistant.workspace import project_locator
from backend.canvas.check_runs import CheckRuns
from backend.canvas.opora_hub import OporaHub
from backend.canvas.sync_report import SyncReport
from backend.code_intelligence import CodeIntelligence
from backend.editor.agent_handoff.message_store import MessageStore
from backend.editor.agent_memory.agent_output import AgentOutput
from backend.editor.agent_memory.agent_workspace import AgentWorkspace
from backend.editor.agent_memory.block_access import BlockAccess
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.agent_packet.desktop_v3_packets import DesktopV3Packets
from backend.editor.agent_packet.node_brief import NodeBrief
from backend.integrations.build_identity import build_identity
from backend.integrations.typesafe_client import evaluate as typesafe_evaluate
from backend.memory.memory_service import AppSettings, MemoryService
from backend.paths import DIST_DIR, REPO_ROOT
from backend.project.maps.map_refresh import MapRefresh
from backend.project.workspace.workspace_sources import WorkspaceSources
from backend.semantic_retrieval.service import SemanticRetrieval


def create_app(data_root=None):
    service = CanvasService(data_root or os.environ.get("OPORA_CANVAS_DATA", ".data/production"))

    desktop_state = DesktopV3State(service)
    service.desktop_v3_state = desktop_state
    # Paměť agenta podle role nad OpenVikingem (samostatný server). Aplikace tudy nespouští
    # žádný model; když je paměť vypnutá nebo server dole, všechno ostatní funguje dál.
    app_settings = AppSettings(service)
    memory_service = MemoryService(settings_store=app_settings)
    service.memory_service = memory_service
    desktop_packets = DesktopV3Packets(service, desktop_state)
    agent_messages = MessageStore(service, desktop_state)
    node_briefs = NodeBrief(service, desktop_state, agent_messages, memory_service=memory_service)
    agent_output = AgentOutput(service, desktop_state)
    block_access = BlockAccess(service, desktop_state)
    agent_workspace = AgentWorkspace(service, desktop_state)
    service.agent_workspace = agent_workspace
    identity = build_identity(service.root)
    map_refresh = MapRefresh(service)
    port = int(os.environ.get("OPORA_CANVAS_PORT", "8740"))
    if not 1 <= port <= 65535:
        raise ValueError("Neplatný lokální port.")
    # Asistent: Claude Code pod předplatným, proces spouští jen zpráva člověka (docs/asistent.md).
    # Skill v jeho procesu čte plátno této instance, ne pevného portu 8740 (§13.1).
    # Směrovač Jev (§13.2): klíč se čte při každé zprávě, takže zapnutí platí bez restartu.
    def route_hint(text, context):
        key = app_settings.typesafe_key()
        return route_message(text, context,
                             evaluate=lambda state, questions: typesafe_evaluate(state, questions, key=key))

    assistant = AssistantManager(service.root, project_locator(service), base_url=f"http://127.0.0.1:{port}",
                                 route_hint=route_hint)

    @asynccontextmanager
    async def lifespan(app):
        map_refresh.start()
        yield
        assistant.close_all()
        map_refresh.close()
        service.close()

    app = FastAPI(title="Opora Canvas", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.service = service
    app.state.map_refresh = map_refresh

    # Vzdálený přístup přes tunel; bez obou proměnných prostředí je hranice přesně dnešní.
    remote = RemoteAccess.from_env()

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        host = request.headers.get("host", "")
        loopback = host in (f"127.0.0.1:{port}", f"localhost:{port}")
        public = not loopback and remote.is_public_host(host)
        if not loopback and not public:
            return JSONResponse({"error": "Nepovolený Host."}, status_code=403)
        # Přes tunel chodí požadavek k nám po HTTP; skutečné schéma nese X-Forwarded-Proto.
        expected_origin = ("http://" + host if loopback
                           else remote.origin_for(host, request.headers.get("x-forwarded-proto")))
        origin = request.headers.get("origin")
        if origin and origin != expected_origin:
            return JSONResponse({"error": "Nepovolený Origin."}, status_code=403)
        if public:
            path = request.url.path
            if is_loopback_only(path):
                return JSONResponse(
                    {"error": "Hook control běží jen na tomto počítači."}, status_code=403
                )
            if requires_token(path) and not remote.authorized(
                    request.headers.get("authorization"), request.cookies.get(COOKIE_NAME)):
                return JSONResponse({"error": TOKEN_REQUIRED}, status_code=401)
        if request.method not in ("GET", "HEAD"):
            if (origin != expected_origin
                    or request.headers.get("content-type", "").split(";")[0] != "application/json"):
                return JSONResponse(
                    {"error": "Zápisy vyžadují stejný Origin a JSON."}, status_code=403
                )
            # Obrázek kresby (do 10 MB, v base64 o třetinu víc) má vlastní strop; ostatní zápisy 2 MB.
            # Dávka plánu (docs/davka-planu.md §3) smí mít celé 2 MiB.
            limit = (14_500_000 if request.url.path == "/api/drawing-file"
                     else 2 * 1024 * 1024 if request.url.path == "/api/canvas-plan" else 2000000)
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > limit:
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
    # hranice vzdáleného přístupu: stav, přihlášení a odhlášení tunelu
    app.include_router(create_access_router(remote, port=port))
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
    app.include_router(create_desktop_v3_router(desktop_state, desktop_packets, node_briefs, agent_output, block_access, agent_workspace, memory_service=memory_service))
    app.include_router(create_agent_message_router(agent_messages))
    app.include_router(create_claude_code_router(service))
    app.include_router(create_assistant_router(assistant, jev_settings=app_settings))
    # RLM: řazení oddílů plátna přes Jev pro asistenta; jen loopback, klíč zůstává v backendu (§13.3)
    app.include_router(create_rlm_router(key_source=app_settings.typesafe_key))
    app.include_router(create_process_router(service))
    # Oracle: echo a verdikt nad zadáním, kódem a gitem; jen čtení, nic nespouští
    check_runs = CheckRuns(service)
    sync_report = SyncReport(service, check_runs=check_runs)
    app.include_router(create_sync_router(sync_report, check_runs))
    # OporaHub: commity zadání a jejich merge; merge pustí jen zelený verdikt Oracle
    app.include_router(create_oporahub_router(service, OporaHub(service), sync_report))
    # LSP-first navigace v kódu; sémantika je lokální fallback, nikdy model spouštěný aplikací
    workspace_sources = WorkspaceSources(service)
    semantic = SemanticRetrieval(workspace_sources)

    def semantic_status():
        detail = semantic.availability_detail()
        return {"status": "unavailable" if detail else "configured",
                "reason": detail or "Local model files are configured; inference remains cold until an explicit query."}

    app.include_router(create_code_intelligence_router(
        service, intelligence=CodeIntelligence(workspace_sources.root, server_cwd=REPO_ROOT, semantic_status=semantic_status)))
    app.include_router(create_semantic_router(service, semantic_service=semantic))
    # Paměť role: stejná vrstva jako sémantika — explicitní dotaz, nikdy automatické volání.
    app.include_router(create_memory_router(service, memory_service))
    # prostředí Live Run
    app.include_router(create_agent_router(service))
    app.include_router(create_node_sessions_router(service))
    app.include_router(create_hook_router(service, port=port))
    app.include_router(create_hook_install_router(service, binding_lookup=service.hook_control.public_binding))

    # Neznámá cesta pod /api je chyba klienta, ne soubor: bez tohohle ji chytne statický
    # mount níž a na POST odpoví 405, což vypadá jako špatná metoda, ne jako překlep v cestě.
    # Existující cestu se špatnou metodou ale 405 popisuje správně, proto se to rozlišuje.
    @app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
                   include_in_schema=False)
    def unknown_api(request: Request, rest: str):
        for route in app.routes:
            if getattr(route, "endpoint", None) is unknown_api:
                continue
            match, _ = route.matches(request.scope)
            if match is Match.PARTIAL:
                return JSONResponse({"error": "Tahle cesta tuhle metodu nepodporuje."},
                                    status_code=405)
        return JSONResponse({"error": "Neznámá cesta API."}, status_code=404)

    dist = DIST_DIR
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="canvas")
    return app
