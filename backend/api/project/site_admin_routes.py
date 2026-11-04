"""Rozhraní Správy webu: dokument projektu, odvozené soubory, assety a fonty (kontrakt Správy webu §2).

Čte kdokoli, zapisuje jen člověk v UI (`require_human`). Srdce (token ověřený zdí, `heart_project`) smí jen podat
návrh změny (`POST /proposals`); přijme ho nebo zamítne jen člověk (S-5, `proposals.py`). Logika
`backend/project/site_admin/`. Stejný Origin a JSON zápisu (i DELETE) a strop těla hlídá middleware aplikace.
"""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from starlette.concurrency import run_in_threadpool

from backend.api.brain_opora.writer import heart_project
from backend.canvas.activity_log import require_human
from backend.canvas.canvas_service import ProjectNotFound
from backend.project.site_admin import compile as compiled
from backend.project.site_admin import proposals, store
from backend.project.site_admin.export import export_zip
from backend.project.site_admin.store import SiteAdminConflict, SiteFileMissing
from backend.project.site_admin.summary import summary
from backend.project.site_admin.tokens import SiteAdminInvalid

PROJECT = Query(min_length=1, max_length=64)
# Soubor z úložiště se v prohlížeči nikdy nespustí: SVG otevřené napřímo nemá skripty ani síť.
FILE_CSP = "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; sandbox"


def _errors(action):
    """404 neznámý projekt nebo soubor, 409 jiná revize, 422 tvar dokumentu nebo souboru."""
    try:
        return action()
    except (ProjectNotFound, SiteFileMissing) as error:
        raise HTTPException(404, str(error)) from error
    except SiteAdminInvalid as error:  # vlastní CSS vrací {message, path, line, reason}
        raise HTTPException(422, getattr(error, "detail", None) or str(error)) from error
    except SiteAdminConflict as error:
        raise HTTPException(409, str(error)) from error


def _human(request, what):
    require_human(getattr(request.state, "actor", "unknown"), f"{what} mění jen člověk na stránce Správa webu.")


def _body(payload, keys):
    if not isinstance(payload, dict) or set(payload) != keys:
        raise HTTPException(422, f"Tělo je přesně {{{', '.join(sorted(keys))}}}.")
    return payload


def create_site_admin_router(service):
    router = APIRouter(prefix="/api/site-admin", tags=["site-admin"])

    def document(project):
        return _errors(lambda: store.read(service, project))

    @router.get("")
    def site_admin_view(project: str = PROJECT):
        current = document(project)
        return {"revision": current["revision"], "document": current}

    @router.put("")
    async def site_admin_save(request: Request, payload: dict, project: str = PROJECT):
        _human(request, "Správu webu")
        if not isinstance(payload, dict) or not {"expectedRevision", "document"} <= set(payload) <= {
                "expectedRevision", "document", "note"}:
            raise HTTPException(422, "Tělo je {expectedRevision, document, note?}.")
        saved, notes = await run_in_threadpool(_errors, lambda: store.write(
            service, project, payload["expectedRevision"], payload["document"], payload.get("note")))
        return {"revision": saved["revision"], "document": saved, "notes": notes}

    @router.get("/tokens.css")
    def tokens_css(project: str = PROJECT):
        return Response(compiled.tokens_css(document(project)), media_type="text/css; charset=utf-8")

    @router.get("/components.css")
    def components_css(project: str = PROJECT):
        return Response(compiled.components_css(document(project)), media_type="text/css; charset=utf-8")

    @router.get("/tokens.json")
    def tokens_json(project: str = PROJECT):
        return Response(compiled.tokens_json(document(project)), media_type="application/json")

    @router.get("/README.md")
    def readme(project: str = PROJECT):
        return Response(compiled.readme(document(project)), media_type="text/markdown; charset=utf-8")

    @router.post("/assets")
    async def asset_upload(request: Request, payload: dict):
        _human(request, "Assety")
        body = _body(payload, {"project", "group", "name", "data"})
        return await run_in_threadpool(_errors, lambda: store.put_asset(
            service, body["project"], body["group"], body["name"], body["data"]))

    @router.delete("/assets")
    def asset_delete(request: Request, project: str = PROJECT, group: str = Query(min_length=1, max_length=64),
                     name: str = Query(min_length=1, max_length=133)):
        _human(request, "Assety")
        _errors(lambda: store.delete_asset(service, project, group, name))
        return {"deleted": f"assets/{group}/{name}"}

    @router.get("/assets/{group}/{name}")
    def asset_file(group: str, name: str, project: str = PROJECT):
        path, media = _errors(lambda: store.asset_path(service, project, group, name))
        return FileResponse(path, media_type=media, headers={"Content-Security-Policy": FILE_CSP})

    @router.post("/fonts")
    async def font_upload(request: Request, payload: dict):
        _human(request, "Fonty")
        body = _body(payload, {"project", "name", "data"})
        return await run_in_threadpool(_errors, lambda: store.put_font(service, body["project"], body["name"], body["data"]))

    @router.delete("/fonts")
    def font_delete(request: Request, project: str = PROJECT, name: str = Query(min_length=1, max_length=133)):
        _human(request, "Fonty")
        _errors(lambda: store.delete_font(service, project, name))
        return {"deleted": f"fonts/{name}"}

    @router.get("/fonts/{name}")
    def font_file(name: str, project: str = PROJECT):
        path, media = _errors(lambda: store.font_path(service, project, name))
        # Náhled komponenty běží v iframu `sandbox=""` s neprůhledným původem; @font-face potřebuje CORS (bez cookies).
        return FileResponse(path, media_type=media, headers={"Content-Security-Policy": FILE_CSP,
                                                             "Access-Control-Allow-Origin": "*"})

    @router.get("/summary")
    def site_admin_summary(project: str = PROJECT):
        """Krátký přehled pro srdce (`opora_heart.py site show`) a počet čekajících návrhů."""
        return {**summary(document(project)), "pendingProposals": len(_errors(lambda: proposals.pending(service, project)))}

    @router.get("/export")
    def site_admin_export(project: str = PROJECT):
        revision, data = _errors(lambda: export_zip(service, project))
        return Response(data, media_type="application/zip", headers={
            "Content-Disposition": 'attachment; filename="design.zip"', "X-Design-Revision": str(revision)})

    @router.get("/proposals")
    def proposal_list(project: str = PROJECT):
        found = _errors(lambda: proposals.pending(service, project))
        return {"proposals": [{key: value for key, value in item.items() if key != "document"} for item in found]}

    @router.post("/proposals")
    async def proposal_create(request: Request, payload: dict):
        if not isinstance(payload, dict) or not {"project", "changes"} <= set(payload) <= {"project", "changes", "note"}:
            raise HTTPException(422, "Tělo je {project, changes, note?}.")
        project = payload["project"]
        heart = heart_project(request) == project
        if not heart:
            _human(request, "Návrh Správy webu")
        found = await run_in_threadpool(_errors, lambda: proposals.propose(
            service, project, payload["changes"], payload.get("note"), "heart" if heart else "human"))
        return {key: value for key, value in found.items() if key != "document"}

    @router.post("/proposals/{proposal_id}/accept")
    async def proposal_accept(request: Request, proposal_id: str, payload: dict):
        _human(request, "Návrh Správy webu")
        body = _body(payload, {"project", "expectedRevision"})
        saved, notes, found = await run_in_threadpool(_errors, lambda: proposals.accept(
            service, body["project"], proposal_id, body["expectedRevision"]))
        return {"revision": saved["revision"], "document": saved, "notes": notes, "proposal": found["id"]}

    @router.post("/proposals/{proposal_id}/reject")
    def proposal_reject(request: Request, proposal_id: str, payload: dict):
        _human(request, "Návrh Správy webu")
        body = _body(payload, {"project"})
        found = _errors(lambda: proposals.reject(service, body["project"], proposal_id))
        return {"proposal": found["id"], "status": found["status"]}

    return router
