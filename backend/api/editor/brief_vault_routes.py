"""Rozhraní Editoru: schránka zadání (docs/navrh-schranka-zadani.md, „API“).

Čtení stromu, fragmentu, historie a balíčku pro LLM (`research-brief`) smí agent i člověk. Zápis je
jedna operace `op`; `set-mvp`, `delete`, `restore` a `feedback` patří člověku, odpověď na otázku pro
člověka také (služba volá `require_human`: agent 403, neznámý původce 428). Chybný tvar požadavku
(`BadRequest`, např. kořen bez disciplíny nebo neznámý filtr `discipline`) je 400; konflikt stavu zůstává 409.
`GET /brief-vault/disciplines` vrací tabulku disciplín s počty živých fragmentů (docs/schranka-neurony.md §2).
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.editor.brief_vault.brief_vault import BriefVault
from backend.editor.brief_vault.brief_vault_model import BadRequest


def _bad_request(call):
    try:
        return call()
    except BadRequest as error:
        return JSONResponse({"error": str(error)}, status_code=400)


def create_brief_vault_router(service, desktop_state=None):
    router = APIRouter(prefix="/api", tags=["brief-vault"])
    vault = BriefVault(service, desktop_state)

    @router.get("/brief-vault")
    def brief_vault_tree(project: str, workspace: str, scope: str | None = None, discipline: str | None = None):
        return _bad_request(lambda: vault.tree(project, workspace, scope, discipline))

    @router.get("/brief-vault/disciplines")
    def brief_vault_disciplines(project: str, workspace: str):
        return vault.disciplines(project, workspace)

    @router.get("/brief-vault/fragment")
    def brief_vault_fragment(project: str, workspace: str, id: str, revision: int | None = None):
        return vault.fragment(project, workspace, id, revision)

    @router.get("/brief-vault/history")
    def brief_vault_history(project: str, workspace: str, scope: str | None = None, limit: int = 300):
        return vault.history(project, workspace, scope, limit)

    @router.get("/brief-vault/research-brief")
    def brief_vault_research_brief(project: str, workspace: str, fragment: str):
        return vault.research_brief(project, workspace, fragment)

    @router.post("/brief-vault")
    def brief_vault_write(payload: dict, request: Request):
        return _bad_request(lambda: vault.apply(payload, actor=request.state.actor, agent=request.state.agent))

    return router
