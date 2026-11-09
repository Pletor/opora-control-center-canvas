"""Rozhraní Editoru: storyboard karty (docs/storyboard-karty.md).

`GET /api/storyboard?project&workspace&nodeId` vrací `{storyboard|null, revision, readOnly, animations}`,
`POST /api/storyboard` ukládá s `expected_revision` (`storyboard: null` smaže). Chyba je `ValueError` → 409.
"""

from fastapi import APIRouter, Query


def create_storyboard_router(storyboard_service):
    router = APIRouter(prefix="/api", tags=["storyboard"])

    @router.get("/storyboard")
    def storyboard_read(project: str, workspace: str, nodeId: str, revision: int | None = Query(None, ge=0)):
        return storyboard_service.read(project, workspace, nodeId, revision)

    @router.post("/storyboard")
    def storyboard_write(payload: dict):
        return storyboard_service.save(payload)

    return router
