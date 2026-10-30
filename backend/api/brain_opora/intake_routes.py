"""Routa vstupní brány požadavků (docs/navrhy/2026-10-30-vstupni-brana.md §6, řez 1).

`GET /api/intake?project=&workspace=` vrací pohled „Požadavky a plán“: oblasti plátna (zatím bez milníku a
požadavků), posledních 50 vstupů a počty `pending` / `duplicates`. Jen čtení; vstupy zapisuje server sám
(zpráva srdce, lístek brány, fragment Schránky), veřejný zápis není. Logika je v
`backend/brain_opora/determinism/intake.py`.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.brain_opora.determinism import intake
from backend.brain_opora.determinism.gate_payloads import GateError


def create_intake_router(service):
    router = APIRouter(prefix="/api/intake", tags=["intake"])

    @router.get("")
    def overview(project: str = "", workspace: str = ""):
        try:
            return intake.overview(service, project, workspace)
        except GateError as error:
            return JSONResponse(error.body(), status_code=error.status)

    return router
