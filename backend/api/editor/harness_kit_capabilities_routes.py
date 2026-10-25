"""Accepted wire-format discovery; never executable-tool or permission discovery."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.canvas.opora_change_validation import scope
from backend.library.harness_kit import MAX_BYTES, MAX_RESOURCES, SUPPORTED_SCHEMAS


def create_harness_kit_capabilities_router(canvas):
    router = APIRouter(tags=["oporahub"])
    headers = {"Cache-Control": "no-store"}

    @router.get("/harness-kit-capabilities")
    def capabilities(project: str, workspace: str):
        try:
            scope({"project": project, "workspace": workspace})
        except ValueError as error:
            return JSONResponse({"error": str(error), "code": "invalid_scope"}, status_code=422, headers=headers)
        if not canvas.project_exists(project):
            return JSONResponse({"error": "Project does not exist.", "code": "project_not_found"}, status_code=404, headers=headers)
        return JSONResponse({
            "schema": "harness.kit-capabilities/1",
            "scope": {"project": project, "workspace": workspace},
            "acceptedKitSchemas": list(SUPPORTED_SCHEMAS),
            "contextProtocolVersion": 2,
            "selectionSchema": "harness.selection/1",
            "limits": {"resources": MAX_RESOURCES, "bytes": MAX_BYTES},
            "evidence": "installed-acceptance-validator",
            "executionAdaptersVerified": False, "permissionsGranted": False,
            "promotionAllowed": False,
        }, headers=headers)

    return router
