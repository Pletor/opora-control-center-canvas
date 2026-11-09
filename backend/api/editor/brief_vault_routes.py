"""Rozhraní Editoru: schránka zadání (docs/navrh-schranka-zadani.md, „API“).

Čtení stromu, fragmentu, historie a balíčku pro LLM (`research-brief`) smí agent i člověk. Zápis je
jedna operace `op`; `set-mvp`, `delete`, `restore` a `feedback` patří člověku, odpověď na otázku pro
člověka také (služba volá `require_human`: agent 403, neznámý původce 428). Chybný tvar požadavku
(`BadRequest`, např. kořen bez disciplíny nebo neznámý filtr `discipline`) je 400; konflikt stavu zůstává 409.
`GET /brief-vault/disciplines` vrací tabulku disciplín s počty živých fragmentů (docs/schranka-neurony.md §2).
`GET /brief-vault/next` je nezávazná fronta bran cyklu a `GET /brief-vault/lessons` živá poučení (§3, §5, §9;
s `versionId` poučení uložené verze plátna). `POST /brief-vault/plan {fragmentIds}` je jen čtení: plán struktury
(oblast → sektor → karty) jako dávka canvas-plan ověřená dryRun, `{plan, summary, hash, skipped, …}` (§4, §9 bod 3).
Odmítnutý plán (i brána `planned`) je 409 `{error, fragments: [{id, title, reason}]}` (`Blocked`).
`GET /brief-vault/duel?id` vrací stav duelu s `probability`, `onTurn`, `rounds`, `canDecide` a `trajectory`;
`GET /brief-vault/vision?scopeNodeId` představu rozsahu s trendem (docs/schranka-duel.md §5).
`GET /brief-vault/mirror` je orientační přehled Zrcadla (docs/zrcadlo.md): `{enabled, health?, byDiscipline, hormones?}`.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.editor.brief_vault.brief_vault import BriefVault
from backend.editor.brief_vault.brief_vault_duel import duel_view, vision_view
from backend.editor.brief_vault.brief_vault_model import BadRequest, Blocked
from backend.editor.brief_vault.brief_vault_next import lessons, next_work


def _bad_request(call):
    try:
        return call()
    except BadRequest as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    except Blocked as error:
        return JSONResponse({"error": str(error), "fragments": error.fragments}, status_code=409)


def create_brief_vault_router(service, desktop_state=None, mirror=None):
    router = APIRouter(prefix="/api", tags=["brief-vault"])
    vault = BriefVault(service, desktop_state, mirror=mirror)

    @router.get("/brief-vault")
    def brief_vault_tree(project: str, workspace: str, scope: str | None = None, discipline: str | None = None):
        return _bad_request(lambda: vault.tree(project, workspace, scope, discipline))

    @router.get("/brief-vault/disciplines")
    def brief_vault_disciplines(project: str, workspace: str):
        return vault.disciplines(project, workspace)

    @router.get("/brief-vault/next")
    def brief_vault_next(project: str, workspace: str, discipline: str | None = None):
        return _bad_request(lambda: next_work(service, project, workspace, discipline))

    @router.get("/brief-vault/lessons")
    def brief_vault_lessons(project: str, workspace: str, discipline: str | None = None, versionId: str | None = None):
        return _bad_request(lambda: lessons(service, project, workspace, discipline, versionId))

    @router.get("/brief-vault/duel")
    def brief_vault_duel(project: str, workspace: str, id: str):
        return _bad_request(lambda: duel_view(service, project, workspace, id))

    @router.get("/brief-vault/vision")
    def brief_vault_vision(project: str, workspace: str, scopeNodeId: str = ""):
        return _bad_request(lambda: vision_view(service, project, workspace, scopeNodeId))

    @router.get("/brief-vault/mirror")
    def brief_vault_mirror(project: str, workspace: str):
        return vault.mirror_overview(project, workspace)

    @router.get("/brief-vault/fragment")
    def brief_vault_fragment(project: str, workspace: str, id: str, revision: int | None = None):
        return vault.fragment(project, workspace, id, revision)

    @router.get("/brief-vault/history")
    def brief_vault_history(project: str, workspace: str, scope: str | None = None, limit: int = 300):
        return vault.history(project, workspace, scope, limit)

    @router.get("/brief-vault/research-brief")
    def brief_vault_research_brief(project: str, workspace: str, fragment: str):
        return vault.research_brief(project, workspace, fragment)

    @router.post("/brief-vault/plan")
    def brief_vault_plan(payload: dict, request: Request):
        # Jen čtení: dávka canvas-plan z fragmentů ověřená dryRun; zapisuje až /api/canvas-plan nebo brána placed.
        return _bad_request(lambda: vault.plan(payload, actor=request.state.actor))

    @router.post("/brief-vault")
    def brief_vault_write(payload: dict, request: Request):
        from backend.brain_opora.determinism import gate, tokens
        from backend.brain_opora.determinism.gate_payloads import GateError
        session = None
        if str(payload.get("op", "")).startswith("duel-") and (
                request.headers.get(tokens.HEADER) or "delegatedRoles" in payload or "delegateRole" in payload):
            try:
                verified = gate.authenticate(service, request.headers.get(tokens.HEADER), payload.get("project"), ("heart", "worker"))
                if verified["role"] == "heart" and verified["workspace_id"] == payload.get("workspace"):
                    session = verified
            except GateError as error:
                return JSONResponse(error.body(), status_code=error.status)
        return _bad_request(lambda: vault.apply(payload, actor=request.state.actor, agent=request.state.agent,
                                                duel_session=session))

    return router
