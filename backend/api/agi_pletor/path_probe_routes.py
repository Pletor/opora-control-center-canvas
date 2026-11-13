"""Průchodový test cesty (docs/navrhy/2026-11-13-denik-chyb.md §11); logika v `backend/app/path_probe.py`.

- `POST /api/pletor/path-probe` → průchod hned (synchronně, bez modelu); agent i člověk. Pískoviště založí jen
  průchod spuštěný člověkem. Souběžný průchod → 409 `path_probe_running`.
- `GET /api/pletor/path-probe?format=json|text` → poslední průchod; text = souhrnná řádka + řádka na krok.
- Lifespan routeru drží denní tik (vlákno; první kontrola po 15 min, průchod jednou za 24 h).
"""
import threading
from contextlib import asynccontextmanager

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from backend.app import path_probe


@asynccontextmanager
async def daily(app):
    stop = threading.Event()
    threading.Thread(target=path_probe.tick_forever, args=(app, stop), name="opora-pruchod-tik", daemon=True).start()
    yield
    stop.set()


def create_path_probe_router():
    router = APIRouter(prefix="/api/pletor", tags=["pletor"], lifespan=daily)

    @router.post("/path-probe")
    def run(request: Request, format: str = "json"):
        if request.state.actor not in ("human", "agent"):
            return JSONResponse({"error": "Průchod spouští identifikovaný agent nebo člověk.",
                                 "code": "identity_required"}, status_code=428)
        result = path_probe.run(request.app, dict(request.cookies) if request.state.actor == "human" else None)
        if result is None:
            return JSONResponse({"error": "Průchod už běží.", "code": "path_probe_running",
                                 "hint": "GET /api/pletor/path-probe?format=text po jeho konci."}, status_code=409)
        return PlainTextResponse(path_probe.text(result)) if format == "text" else result

    @router.get("/path-probe")
    def read(request: Request, format: str = "json"):
        result = path_probe.last(request.app.state.service.root)
        return PlainTextResponse(path_probe.text(result)) if format == "text" else {"last": result}

    return router
