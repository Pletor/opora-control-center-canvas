"""Rozhraní Editoru: commity OporaHubu nad zadáním rozsahu a jejich merge do mainu.

Commit zapisuje revizi zadání a otisk grafu; obsah bere z aplikace, ne z těla požadavku,
aby zápis nemohl tvrdit něco jiného, než co je uložené. Merge projde jen rozsahu, kterému
to Oracle dovolí (`canMerge`). Agent nesmí ani jedno — hlídá to `OporaHub`.
"""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from backend.editor.agent_packet.specification_context import capture_specification


def create_oporahub_router(service, hub, report):
    router = APIRouter(prefix="/api", tags=["oporahub"])

    def author(payload):
        by = payload.get("by")
        if not isinstance(by, dict):
            raise ValueError("Chybí autor zápisu (by).")  # noqa: TRY004 — API mapuje na 409
        return {"kind": by.get("kind"), "name": by.get("name")}

    @router.post("/opora-commit")
    def commit(payload: dict):
        pid = payload.get("project")
        wid = payload.get("workspace") or "draft"
        scope_id = payload.get("scope")
        with service.graph_lock, service.lock:
            view = service.view(pid, wid)
            node = next((item for item in view["graph"]["nodes"] if item["id"] == scope_id), None)
            if node is None:
                return JSONResponse({"error": "Rozsah v tomto pracovním prostoru neexistuje."},
                                    status_code=404)
            spec = service.specs.read((pid, wid, scope_id))
            snapshot = capture_specification(service, pid, wid, scope_id)
            return hub.commit((pid, wid, scope_id), {
                "kind": node["kind"],
                "specRevision": spec["revision"],
                "graphDigest": view["digest"],
                "subject": payload.get("subject") or f"zadání revize {spec['revision']}",
                "by": author(payload),
                "pair": None,
                "specificationSnapshot": snapshot,
            })

    @router.get("/opora-commit")
    def read_commit(
        project: str = Query(min_length=1, max_length=64),
        workspace: str = Query(default="draft", min_length=1, max_length=64),
        scope: str = Query(min_length=1, max_length=80),
        id: str = Query(min_length=40, max_length=40),
    ):
        return hub.read((project, workspace, scope), id)

    @router.get("/opora-commits")
    def history(
        project: str = Query(min_length=1, max_length=64),
        workspace: str = Query(default="draft", min_length=1, max_length=64),
        scope: str = Query(min_length=1, max_length=80),
        limit: int = Query(default=20, ge=1, le=100),
    ):
        items = hub.history((project, workspace, scope), limit)
        return {"items": items, "head": hub.head((project, workspace, scope)),
                "main": hub.main_of((project, workspace, scope))}

    @router.post("/opora-merge")
    def merge(payload: dict):
        pid = payload.get("project")
        wid = payload.get("workspace") or "draft"
        scope_id = payload.get("scope")
        by = author(payload)
        verdict = _verdict_of(report.report(pid, wid), scope_id)
        if verdict is None:
            return JSONResponse({"error": "Rozsah nemá verdikt; merge nelze posoudit."},
                                status_code=404)
        if not verdict["canMerge"]:
            return JSONResponse({
                "error": "Brána 1:1 je zavřená; merge se neprovádí.",
                "blocking": verdict["blocking"],
                "nextSteps": verdict["nextSteps"],
            }, status_code=409)
        return hub.merge((pid, wid, scope_id), payload.get("id"), by=by)

    return router


def _verdict_of(payload, scope_id):
    return next((item for item in payload["verdicts"] if item["scope"]["id"] == scope_id), None)
