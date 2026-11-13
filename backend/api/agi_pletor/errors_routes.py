"""Deník chyb OPORY, jen čtení (docs/navrhy/2026-11-13-denik-chyb.md §5). Čte agent i člověk; logika v `backend/app/errors.py`.

- `GET /api/pletor/errors?project=&open=1&since=&kind=&source=&limit=200&format=json|text` →
  `{errors: [záznam], open}`; `format=text` jsou řádky pro agenta (otevřené podle závažnosti a počtu).
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse, PlainTextResponse

from backend.app import errors
from backend.brain_opora.determinism.gate_payloads import invalid


def create_errors_router():
    router = APIRouter(prefix="/api/pletor", tags=["pletor"])

    @router.get("/errors")
    def read_errors(project: str = "", open: int = 1, since: str = "", kind: str = "", source: str = "",
                    limit: int = 200, format: str = "json"):
        if not 1 <= limit <= 1000:
            return JSONResponse(invalid("limit je číslo 1–1000.", "Příklad: ?limit=200").body(), status_code=422)
        rows = errors.read(project=project or None, open_only=bool(open), since=since or None, kind=kind or None,
                           source=source or None, limit=limit)
        if format == "text":
            return PlainTextResponse(errors.text(rows))
        return {"errors": rows, "open": errors.counts(project or None)["open"]}

    return router
