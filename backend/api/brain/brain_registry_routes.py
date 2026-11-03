"""API registru Brainu (`backend/brain/registry.py`, kontrakt `docs/navrhy/2026-11-03-novy-zaklad.md` §3.4), jen čtení.

Tenký router: data leží v registry.sqlite, každé volání drží `registry_lock`. Zip pinu (`Store.export`) čte dělník
téhož stroje; přes veřejný tunel ho hranice v `backend/app/factory.py` pustí jen s přístupovým tokenem.
"""

import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.brain import registry
from backend.brain.store import NAME, Store

SHORT = re.compile(r"[0-9a-f]{12}")


def create_brain_registry_router(service):
    router = APIRouter(prefix="/api/brain-registry", tags=["brain-registry"])

    @router.get("/artifacts")
    def artifact_list():
        with service.registry_lock:
            return {"artifacts": registry.list_artifacts(service.db)}

    @router.get("/artifacts/{artifact_id}")
    def artifact_detail(artifact_id: str):
        with service.registry_lock:
            artifact = registry.get_artifact(service.db, artifact_id)
        if artifact is None:
            raise HTTPException(404, "Artefakt Brainu neexistuje.")
        return artifact

    @router.get("/pins/{plugin}@{sha12}.zip")
    def pin_zip(plugin: str, sha12: str):
        sha = None
        if NAME.fullmatch(plugin) and SHORT.fullmatch(sha12):
            with service.registry_lock:
                sha = registry.plugin_version(service.db, plugin, sha12)
        if sha is None:
            raise HTTPException(404, "Verze pluginu v registru Brainu není.")
        return FileResponse(Store(service.root).export(plugin, sha), media_type="application/zip",
                            filename=f"{plugin}@{sha12}.zip")

    return router
