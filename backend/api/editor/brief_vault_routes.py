"""Rozhraní Editoru: schránka zadání (docs/navrh-schranka-zadani.md, „API“).

Čtení stromu a fragmentu smí agent i člověk. Zápis je jedna operace `op`; `set-mvp`, `delete`
a `restore` patří člověku (služba volá `require_human`: agent 403, neznámý původce 428).
"""

from fastapi import APIRouter, Request

from backend.editor.brief_vault.brief_vault import BriefVault


def create_brief_vault_router(service, desktop_state=None):
    router = APIRouter(prefix="/api", tags=["brief-vault"])
    vault = BriefVault(service, desktop_state)

    @router.get("/brief-vault")
    def brief_vault_tree(project: str, workspace: str, scope: str | None = None):
        return vault.tree(project, workspace, scope)

    @router.get("/brief-vault/fragment")
    def brief_vault_fragment(project: str, workspace: str, id: str, revision: int | None = None):
        return vault.fragment(project, workspace, id, revision)

    @router.post("/brief-vault")
    def brief_vault_write(payload: dict, request: Request):
        return vault.apply(payload, actor=request.state.actor, agent=request.state.agent)

    return router
