import os
import re
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.routing import Match

from backend.api.access_routes import create_access_router
from backend.api.app_routes import create_app_router
from backend.api.editor.activity_log_routes import create_activity_log_router
from backend.api.editor.agent_message_routes import create_agent_message_router
from backend.api.editor.assistant_routes import create_assistant_router
from backend.api.editor.brief_vault_check_routes import create_brief_vault_check_router
from backend.api.editor.brief_vault_routes import create_brief_vault_router
from backend.api.editor.canvas_routes import create_canvas_router
from backend.api.editor.canvas_version_routes import create_canvas_version_router
from backend.api.editor.claude_code_routes import create_claude_code_router
from backend.api.editor.code_intelligence_routes import create_code_intelligence_router
from backend.api.editor.desktop_v3_routes import create_desktop_v3_router
from backend.api.editor.harness_learning_routes import create_harness_learning_router
from backend.api.editor.harness_invocation_routes import create_harness_invocation_router
from backend.api.editor.memory_routes import create_memory_router
from backend.api.editor.node_routes import create_node_router
from backend.api.editor.opora_agent_state_routes import create_opora_agent_state_router
from backend.api.editor.opora_auto_rebase_routes import create_opora_auto_rebase_router
from backend.api.editor.opora_changeset_routes import create_opora_changeset_router
from backend.api.editor.opora_content_routes import CONTENT_BODY_LIMIT, create_opora_content_router
from backend.api.editor.opora_design_preview_routes import MAX_BODY as PREVIEW_BODY_LIMIT
from backend.api.editor.opora_design_preview_routes import create_design_preview_router
from backend.api.editor.opora_event_routes import create_opora_event_router
from backend.api.editor.opora_execution_budget_routes import create_execution_budget_router
from backend.api.editor.opora_execution_observer_routes import BODY_LIMIT as OBSERVER_BODY_LIMIT
from backend.api.editor.opora_execution_observer_routes import create_execution_observer_router
from backend.api.editor.opora_execution_pull_request_routes import (
    create_execution_pull_request_router,
)
from backend.api.editor.opora_execution_routes import create_opora_execution_router
from backend.api.editor.opora_folder_repository_routes import create_folder_repository_router
from backend.api.editor.opora_graph_routes import create_opora_graph_router
from backend.api.editor.opora_history_routes import create_opora_history_router
from backend.api.editor.opora_plan_lens_routes import create_plan_lens_router
from backend.api.editor.opora_process_routes import create_opora_process_router
from backend.api.editor.opora_proposal_review_routes import create_proposal_review_router
from backend.api.editor.opora_proposal_routes import create_opora_proposal_router
from backend.api.editor.opora_reconciliation_routes import create_opora_reconciliation_router
from backend.api.editor.opora_review_insight_routes import create_review_insight_router
from backend.api.editor.opora_review_job_routes import create_review_job_router
from backend.api.editor.opora_review_lens_routes import create_review_lens_router
from backend.api.editor.opora_review_policy_routes import create_opora_review_policy_router
from backend.api.editor.opora_review_routes import create_opora_review_router
from backend.api.editor.opora_review_self_check_routes import create_review_self_check_router
from backend.api.editor.opora_verification_routes import BODY_LIMIT as VERIFICATION_BODY_LIMIT
from backend.api.editor.opora_verification_routes import create_opora_verification_router
from backend.api.editor.oporahub_process_event_routes import INGEST_PATH as PROCESS_INGEST_PATH
from backend.api.editor.oporahub_process_event_routes import create_process_event_router
from backend.api.editor.oporahub_routes import create_oporahub_router
from backend.api.editor.rlm_routes import create_rlm_router
from backend.api.editor.semantic_routes import create_semantic_router
from backend.api.editor.storyboard_routes import create_storyboard_router
from backend.api.editor.sync_routes import create_sync_router
from backend.api.project.archify_routes import create_archify_router
from backend.api.project.design_system_routes import create_design_system_router
from backend.api.project.graphify_routes import create_graphify_router
from backend.api.project.map_refresh_routes import create_map_refresh_router
from backend.api.project.project_architecture_routes import create_project_architecture_router
from backend.api.project.project_web_status_routes import create_project_web_status_router
from backend.api.project.project_work_status_routes import create_project_work_status_router
from backend.api.project.project_workspace_routes import create_project_workspace_router
from backend.api.project.workspace_routes import create_workspace_router
from backend.api.project_setup.project_routes import create_project_setup_router
from backend.app.embed_origins import ENV_NAME as EMBED_ORIGINS_ENV
from backend.app.embed_origins import frame_policy, parse_embed_origins
from backend.app.human_session import HumanSession
from backend.app.remote_access import (
    COOKIE_NAME,
    TOKEN_REQUIRED,
    RemoteAccess,
    is_loopback_only,
    requires_token,
)
from backend.canvas.activity_log import ActivityLog, HumanRequired, describe
from backend.canvas.canvas_service import CanvasService, ProjectNotFound
from backend.canvas.check_runs import CheckRuns
from backend.canvas.opora_auto_rebase_manager import AutoRebaseManager
from backend.canvas.opora_execution_pr_manager import ExecutionPullRequestManager
from backend.canvas.opora_hub import OporaHub
from backend.canvas.opora_reconciliation_manager import ReconciliationManager
from backend.canvas.process_activity_bridge import bridge as bridge_activity
from backend.canvas.sync_report import SyncReport
from backend.claude_code.assistant.agents import load_agents
from backend.claude_code.assistant.manager import AssistantManager
from backend.claude_code.assistant.router import route as route_message
from backend.claude_code.assistant.workspace import project_locator
from backend.code_intelligence import CodeIntelligence
from backend.editor.agent_handoff.message_store import MessageStore
from backend.editor.agent_memory.agent_output import AgentOutput
from backend.editor.agent_memory.agent_workspace import AgentWorkspace
from backend.editor.agent_memory.block_access import BlockAccess
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.agent_packet.desktop_v3_packets import DesktopV3Packets
from backend.editor.agent_packet.node_brief import NodeBrief
from backend.editor.storyboard.storyboard import StoryboardService
from backend.integrations.build_identity import build_identity
from backend.integrations.typesafe_client import configured_provider
from backend.integrations.typesafe_client import evaluate as typesafe_evaluate
from backend.library.harness_memory import HarnessMemory
from backend.memory.memory_service import AppSettings, MemoryService
from backend.paths import DIST_DIR, REPO_ROOT
from backend.project.architecture.web_status import WebStatusService
from backend.project.maps.map_refresh import MapRefresh
from backend.project.workspace.workspace_sources import WorkspaceSources
from backend.project.worktrees.workspace_archive import WorkspaceArchive
from backend.semantic_retrieval.service import SemanticRetrieval

WORKER_SCRIPT = re.compile(r"/assets/code-animation\.worker-[A-Za-z0-9_-]+\.js")


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
    storyboards = StoryboardService(service)
    service.sketch_layers_provider = storyboards.sketch_layers
    service.sketch_stale_callback = storyboards.mark_sketch_stale
    node_briefs = NodeBrief(service, desktop_state, agent_messages, memory_service=memory_service, storyboard=storyboards)
    agent_output = AgentOutput(service, desktop_state)
    block_access = BlockAccess(service, desktop_state)
    agent_workspace = AgentWorkspace(service, desktop_state)
    service.agent_workspace = agent_workspace
    identity = build_identity(service.root)
    map_refresh = MapRefresh(service)
    reconciliation = ReconciliationManager(service)
    execution_prs = ExecutionPullRequestManager(service)
    auto_rebase = AutoRebaseManager(service)
    harness_memory = HarnessMemory(service, memory_service)
    port = int(os.environ.get("OPORA_CANVAS_PORT", "8740"))
    if not 1 <= port <= 65535:
        raise ValueError("Neplatný lokální port.")
    # Rámování jen pro původy z [app] embed_origins; prázdné = DENY jako dřív (backend/app/embed_origins.py).
    frame_options, frame_ancestors = frame_policy(parse_embed_origins(os.environ.get(EMBED_ORIGINS_ENV, "")))
    # Asistent: Claude Code pod předplatným, proces spouští jen zpráva člověka (docs/asistent.md).
    # Skill v jeho procesu čte plátno této instance, ne pevného portu 8740 (§13.1).
    # Směrovač Jev (§13.2): klíč se čte při každé zprávě, takže zapnutí platí bez restartu.
    # Poskytovatel Jev (typesafe | celeris) z `[jev] provider` v opora.local.toml (docs/schranka-neurony.md §7).
    jev_provider = configured_provider()

    def jev_evaluate(state, questions, *, key):
        return typesafe_evaluate(state, questions, key=key, provider=jev_provider)

    def route_hint(text, context):
        key = app_settings.jev_key(jev_provider)
        return route_message(text, context,
                             evaluate=lambda state, questions: jev_evaluate(state, questions, key=key))

    assistant = AssistantManager(service.root, project_locator(service), base_url=f"http://127.0.0.1:{port}",
                                 route_hint=route_hint, route_provider=jev_provider,
                                 instructions=lambda: app_settings.assistant_instructions()["text"],
                                 agents=load_agents)

    @asynccontextmanager
    async def lifespan(app):
        map_refresh.start()
        reconciliation.start()
        execution_prs.start()
        auto_rebase.start()
        harness_memory.start()
        yield
        assistant.close_all()
        map_refresh.close()
        reconciliation.close()
        execution_prs.close()
        auto_rebase.close()
        harness_memory.close()
        service.close()

    app = FastAPI(title="Opora Canvas", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.service = service
    app.state.map_refresh = map_refresh
    app.state.reconciliation = reconciliation

    # Vzdálený přístup přes tunel; bez obou proměnných prostředí je hranice přesně dnešní.
    remote = RemoteAccess.from_env()

    activity_log = ActivityLog(service)
    # Člověk = relační doklad UI, ne chybějící hlavička (upgrade-opora #29).
    human = HumanSession()

    def _log_activity(request, status):
        """Záznam činnosti (docs/zaznam-cinnosti.md); jeho selhání nikdy neshodí požadavek."""
        if request.url.path == PROCESS_INGEST_PATH:
            return  # příjem živého procesu má vlastní tok (outbox); v záznamu činnosti by jen spamoval
        try:
            actor, agent = request.state.actor, request.state.agent
            described = describe(getattr(request, "_body", b""), dict(request.query_params))
            activity_log.record(actor=actor, agent=agent, method=request.method, path=request.url.path,
                                described=described, status=status)
            # Živý proces: paměť a starý commit zadání nemají událost v outboxu (docs/zivy-proces.md §4).
            bridge_activity(service, method=request.method, path=request.url.path, status=status, actor=actor,
                            agent=agent, described=described)
        except Exception:  # noqa: BLE001 - záznam je doplněk, ne podmínka zápisu
            return

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
        request.state.actor, request.state.agent = human.actor(request.headers, request.cookies)
        if origin and origin != expected_origin:
            return JSONResponse({"error": "Nepovolený Origin."}, status_code=403)
        if public:
            path = request.url.path
            if is_loopback_only(path):
                return JSONResponse(
                    {"error": "Tohle běží jen na tomto počítači."}, status_code=403
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
            limit = (OBSERVER_BODY_LIMIT if request.url.path.startswith("/api/oporahub/execution-observers/")
                     else VERIFICATION_BODY_LIMIT if request.url.path.startswith("/api/oporahub/verifications/")
                     else CONTENT_BODY_LIMIT if request.url.path == "/api/oporahub/content-changes" or request.url.path.startswith("/api/oporahub/content-changes/")
                     else 14_500_000 if request.url.path == "/api/drawing-file"
                     else PREVIEW_BODY_LIMIT if request.url.path == "/api/oporahub/review-jobs/preview"
                     else 2 * 1024 * 1024 if request.url.path == "/api/canvas-plan" else 2000000)
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > limit:
                    return JSONResponse({"error": "Požadavek je příliš velký."}, status_code=413)
                body.extend(chunk)
            request._body = bytes(body)
        response = await call_next(request)
        if request.method not in ("GET", "HEAD") and request.url.path.startswith("/api"):
            _log_activity(request, response.status_code)
        response.headers["X-Content-Type-Options"] = "nosniff"
        if frame_options:
            response.headers["X-Frame-Options"] = frame_options
        response.headers["Referrer-Policy"] = "no-referrer"
        # Obrázky jen z vlastního původu, data:/blob: a https (upgrade-opora #42); http beacon ani <object> ne.
        baseline_csp = "img-src 'self' data: blob: https:; object-src 'none'; base-uri 'self'; " + frame_ancestors
        route_csp = response.headers.get("Content-Security-Policy")
        if WORKER_SCRIPT.fullmatch(request.url.path):
            # Worker kódu animace (docs/storyboard-karty.md): převzatý modul smí importovat jen z blob:, vnořený Worker
            # jen z blob: (dědí tuto CSP) a nemá síť. Vypnuté fetch v kódu je jen druhá pojistka; tohle hlídá prohlížeč.
            route_csp = "default-src 'none'; script-src blob:; worker-src blob:; connect-src 'none'"
        response.headers["Content-Security-Policy"] = (route_csp + ", " + baseline_csp) if route_csp else baseline_csp
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(HumanRequired)
    async def human_required(request, exc):
        # 428: UI si obnoví doklad a zkusí to znovu; agent dostane jasné 403.
        return JSONResponse({"error": str(exc), "humanRequired": True},
                            status_code=403 if exc.actor == "agent" else 428)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"error": str(exc)}, status_code=409)

    @app.exception_handler(ProjectNotFound)
    async def missing_project(request, exc):
        # Neznámé ID projektu (i jiná velikost písmen): nic se nezaloží ani neotevře (karta P3).
        return JSONResponse({"error": str(exc)}, status_code=404)

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
    app.include_router(create_access_router(remote, port=port, human=human))
    # krok 1: nastavení projektu
    app.include_router(create_project_setup_router(service))
    # prostředí Projekt
    app.include_router(create_project_workspace_router(service, WorkspaceArchive(service, assistant.registry)))
    app.include_router(create_workspace_router(service))
    app.include_router(create_archify_router(service))
    app.include_router(create_graphify_router(service))
    app.include_router(create_map_refresh_router(map_refresh))
    app.include_router(create_project_architecture_router(service))
    # prostředí Editor
    app.include_router(create_canvas_router(service))
    app.include_router(create_storyboard_router(storyboards))
    app.include_router(create_canvas_version_router(service, desktop_state))
    app.include_router(create_activity_log_router(activity_log))
    app.include_router(create_node_router(service))
    # Schránka zadání: doslovné verzované fragmenty a odkazy karet (docs/navrh-schranka-zadani.md)
    app.include_router(create_brief_vault_router(service, desktop_state))
    # Poradní kontrola brány přes Jev; jen s povolením člověka pro projekt a poskytovatele (§9 bod 10)
    app.include_router(create_brief_vault_check_router(service, settings=app_settings, provider=jev_provider))
    app.include_router(create_desktop_v3_router(desktop_state, desktop_packets, node_briefs, agent_output, block_access, agent_workspace, memory_service=memory_service))
    app.include_router(create_agent_message_router(agent_messages))
    app.include_router(create_claude_code_router(service))
    app.include_router(create_assistant_router(assistant, jev_settings=app_settings, jev_provider=jev_provider))
    # RLM: řazení oddílů plátna přes Jev pro asistenta; jen loopback, klíč zůstává v backendu (§13.3)
    app.include_router(create_rlm_router(key_source=lambda: app_settings.jev_key(jev_provider), evaluate=jev_evaluate))
    app.include_router(create_project_work_status_router(service, assistant.registry))
    app.include_router(create_project_web_status_router(WebStatusService(service)))
    # Oracle: echo a verdikt nad zadáním, kódem a gitem; jen čtení, nic nespouští
    check_runs = CheckRuns(service)
    sync_report = SyncReport(service, check_runs=check_runs)
    app.include_router(create_sync_router(sync_report, check_runs))
    # OporaHub: commity zadání a jejich merge; merge pustí jen zelený verdikt Oracle
    app.include_router(create_oporahub_router(service, OporaHub(service), sync_report))
    app.include_router(create_opora_proposal_router(service, OporaHub(service)))
    app.include_router(create_opora_changeset_router(service))
    app.include_router(create_opora_review_router(service))
    app.include_router(create_opora_review_policy_router(service))
    app.include_router(create_opora_reconciliation_router(service))
    # Projekt z lokální složky: člověk připojí GitHub repozitář jejího origin (docs/oporahub-github.md)
    app.include_router(create_folder_repository_router(service))
    app.include_router(create_opora_execution_router(service))
    app.include_router(create_harness_invocation_router(service))
    app.include_router(create_execution_pull_request_router(service))
    app.include_router(create_review_self_check_router(service))  # before /{job}/… review job paths
    app.include_router(create_review_lens_router(service))  # POST /review-jobs/lens, GET /review-lens
    app.include_router(create_design_preview_router(service))  # evidence.preview, Potvrdit vzhled, design-mode
    app.include_router(create_design_system_router(service))  # GET /design-system (DESIGN.md z HEAD)
    app.include_router(create_plan_lens_router(service, desktop_state))  # GET /plan-lens (docs/plan-lens.md)
    app.include_router(create_review_job_router(service))
    app.include_router(create_review_insight_router(service))
    app.include_router(create_opora_process_router(service))
    app.include_router(create_opora_agent_state_router(service))
    # Živý tok událostí OporaHubu (outbox, kurzor + SSE), jen čtení (docs/oporahub-events.md)
    app.include_router(create_opora_event_router(service))
    app.include_router(create_process_event_router(service, memory_status=memory_service.status))
    app.include_router(create_harness_learning_router(service))
    app.include_router(create_execution_observer_router(service))
    app.include_router(create_opora_verification_router(service))
    app.include_router(create_execution_budget_router(service))
    app.include_router(create_opora_graph_router(service))
    app.include_router(create_opora_content_router(service))
    app.include_router(create_proposal_review_router(service))
    app.include_router(create_opora_auto_rebase_router(service))
    app.include_router(create_opora_history_router(service))
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
