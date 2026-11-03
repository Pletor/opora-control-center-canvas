"""API registru Brainu (`backend/brain/registry.py`, kontrakt `docs/navrhy/2026-11-03-novy-zaklad.md` §3.4), jen čtení.

Tenký router: data leží v registry.sqlite, každé volání drží `registry_lock`.
"""

from fastapi import APIRouter, HTTPException

from backend.brain import registry


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

    return router
