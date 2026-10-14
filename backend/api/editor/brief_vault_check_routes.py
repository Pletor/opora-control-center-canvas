"""Rozhraní Editoru: poradní kontrola brány Schránky přes Jev (docs/schranka-neurony.md §7, §9 bod 10).

`POST /api/brief-vault/gate-check {project, workspace, fragmentId, expectedRevision, gate, payload}` smí agent
i člověk; nic nezapisuje. Bez povolení člověka pro (projekt, poskytovatel) neodejde žádný síťový požadavek.
Chybný tvar = 400, jiná revize nebo neexistující fragment = 409. Klíč se čte při každém dotazu a nikdy
se nevrací. Cesta je jen loopback (`backend/app/remote_access.py`), protože volá placené API klíčem aplikace.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.editor.brief_vault.brief_vault_check import gate_check
from backend.editor.brief_vault.brief_vault_model import BadRequest
from backend.integrations.typesafe_client import DEFAULT_PROVIDER
from backend.integrations.typesafe_client import evaluate as typesafe_evaluate


def create_brief_vault_check_router(service, *, settings=None, provider=DEFAULT_PROVIDER, evaluate=typesafe_evaluate):
    router = APIRouter(prefix="/api", tags=["brief-vault"])

    @router.post("/brief-vault/gate-check")
    def brief_vault_gate_check(payload: dict):
        try:
            return gate_check(service, payload, settings=settings, provider=provider, evaluate=evaluate)
        except BadRequest as error:
            return JSONResponse({"error": str(error)}, status_code=400)
        except ValueError as error:
            return JSONResponse({"error": str(error)}, status_code=409)

    return router
