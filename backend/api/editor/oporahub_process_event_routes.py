"""Živý proces OporaHubu (docs/zivy-proces.md): příjem z kanceláře a zdraví zdrojů.

Události se čtou jediným tokem `/api/oporahub/events` a `/events/stream` (opora_event_routes).
Zápis smí jen agent (`X-Opora-Actor: agent; name=…`) se stejným Originem a JSON jako ostatní
agentní zápisy (hranice v `backend/app/factory.py`); UI člověka k němu není potřeba.
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.canvas.process_ingest import health, ingest

INGEST_PATH = "/api/oporahub/process-events"


def create_process_event_router(canvas, *, memory_status=None):
    router = APIRouter(prefix="/api/oporahub", tags=["oporahub"])

    @router.post("/process-events")
    def receive(payload: dict, request: Request):
        actor = request.state.actor
        if actor == "unknown":
            return JSONResponse({"error": "Zápis živého procesu vyžaduje X-Opora-Actor agenta.",
                                 "code": "identity_required"}, status_code=428)
        if actor != "agent":
            return JSONResponse({"error": "Události procesu posílá jen agent (kancelář).",
                                 "code": "agent_required"}, status_code=403)
        try:
            result = ingest(canvas, payload, poster=request.state.agent or "office")
        except ValueError as error:
            return JSONResponse({"error": str(error), "code": "invalid_batch"}, status_code=422)
        if result["rejected"] and not (result["accepted"] or result["duplicates"]):
            return JSONResponse({**result, "error": "Žádná událost neprošla kontraktem."}, status_code=422)
        return result

    @router.get("/process-health")
    def process_health(project: str, workspace: str):
        if not canvas.project_exists(project):
            return JSONResponse({"error": "Projekt neexistuje.", "code": "project_not_found"}, status_code=404)
        status = None
        if memory_status is not None:
            try:
                status = memory_status()
            except Exception as error:  # noqa: BLE001 - zdraví paměti nesmí shodit přehled
                status = {"status": "unavailable", "reason": str(error)[:200]}
        return health(canvas, project, workspace, memory_status=status)

    return router
