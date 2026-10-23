"""`GET /api/oporahub/design-system?project=`: DESIGN.md projektu z commitnuté revize (docs/design-nahled.md §2)."""
from fastapi import APIRouter, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from backend.api.editor.opora_design_preview_routes import identity
from backend.api.http_etag import conditional, etag_of
from backend.project.design import design_system


def create_design_system_router(service):
    router = APIRouter(prefix="/api/oporahub", tags=["oporahub"])

    @router.get("/design-system")
    async def read(request: Request, project: str = Query(min_length=1, max_length=64)):
        if identity(request) is None:
            return JSONResponse({"error": "Review identity is required.", "code": "identity_required"},
                                status_code=428)
        # Obsah se drží v paměti podle blobu, takže opakované čtení stojí jen `rev-parse`; ETag je z revize a otisku.
        value = await run_in_threadpool(design_system.read, service, project)
        reference = {key: item for key, item in value.items() if key != "markdown"}
        return conditional(request, etag_of("design-system", project, reference), lambda: value)

    return router
