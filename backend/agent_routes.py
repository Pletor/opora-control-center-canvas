"""Jeden router factory pro observabilitu agentů (WU-AGENT-OBSERVABILITY).

Integrace rodičem: v `backend/app.py` po vytvoření `service`/`app` přidat

    from .agent_routes import create_agent_router
    app.include_router(create_agent_router(service))

Router nic nespouští ani nezastavuje; všechny endpointy jsou GET (čtení) kromě
explicitního potvrzení vazby (`POST /api/agents/bindings`) a explicitního
zachycení bezpečného náhledu aktivity (`POST /api/agents/activity`), obě
požadují stejná Origin/JSON pravidla jako zbytek `app.py` boundary middleware.
"""

import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .agent_activity import AgentActivityJournal
from .agent_bindings import AgentBindings
from .agent_catalog import AgentCatalog, UnknownSource
from .agent_sources import LocalOrchestratorSource, PlatnoSource

DEFAULT_ORCHESTRATOR_ROOT = (
    r"C:\Users\Admin\AppData\Local\hermes\handoffs\canvas-orchestration"
)


def create_agent_router(service, *, platno_base_url=None, orchestrator_root=None):
    platno = PlatnoSource(platno_base_url or os.environ.get("OPORA_AGENT_PLATNO_URL", "http://127.0.0.1:8738"))
    orchestrator_root = orchestrator_root or os.environ.get("OPORA_AGENT_ORCHESTRATOR_ROOT", DEFAULT_ORCHESTRATOR_ROOT)
    orchestrator = LocalOrchestratorSource(orchestrator_root) if orchestrator_root else None
    catalog = AgentCatalog(platno=platno, orchestrator=orchestrator)
    known_sources = [platno.source_id] + ([orchestrator.source_id] if orchestrator else [])
    bindings = AgentBindings(service, known_sources=known_sources)
    activity = AgentActivityJournal(service)

    router = APIRouter(prefix="/api/agents", tags=["agents"])

    @router.get("/sources")
    def sources():
        return catalog.source_health()

    @router.get("/runs")
    def list_runs(source: str | None = None, limit: int = 20, cursor: int = 0):
        return catalog.list_runs(source_id=source, limit=limit, cursor=cursor)

    @router.get("/runs/{source_id}/{run_id}")
    def run_detail(source_id: str, run_id: str):
        try:
            return catalog.run_detail(source_id, run_id)
        except UnknownSource:
            return JSONResponse({"error": "Neznámý zdroj běhů agenta."}, status_code=404)
        except ValueError:
            return JSONResponse({"error": "Neplatný nebo nedostupný identifikátor běhu."}, status_code=404)

    @router.get("/unbound")
    def unbound(source: str | None = None, limit: int = 20):
        page = catalog.list_runs(source_id=source, limit=limit)
        candidates = [{"sourceId": r["sourceId"], "runId": r["runId"]} for r in page["items"]]
        return {"items": bindings.filter_unbound(candidates)}

    @router.post("/bindings")
    def create_binding(payload: dict):
        return bindings.bind(payload)

    @router.get("/bindings")
    def list_bindings(project: str, workspace: str, nodeId: str):
        return bindings.list_for_node(project, workspace, nodeId)

    @router.get("/bindings/sector")
    def sector_bindings(project: str, workspace: str, nodeId: str):
        return bindings.sector_aggregate(project, workspace, nodeId)

    @router.post("/activity")
    def capture_activity(payload: dict):
        return activity.capture(payload)

    @router.get("/activity")
    def list_activity(project: str, workspace: str, nodeId: str):
        return activity.list_for_node(project, workspace, nodeId)

    return router
