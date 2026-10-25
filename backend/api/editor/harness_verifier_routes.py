"""Request a native-owned check; worker input contains references, never observed results."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.canvas.opora_execution_observer_auth import strict_json
from backend.canvas.opora_verifications import OporaVerifications
from backend.library.harness_stability import HarnessStability
from backend.library.harness_stability_retained import RetainedStability
from backend.library.harness_transfer import SharedEligibility
from backend.library.harness_verifier import HarnessVerifier
from backend.library.harness_verifier_budget import read as capacity
from backend.library.harness_verifier_quarantine import read as quarantine


def create_harness_verifier_router(canvas):
    router = APIRouter(prefix="/api/oporahub/harness-verifier", tags=["oporahub"])
    verifier = HarnessVerifier(canvas)

    @router.get("/requests")
    async def history(request: Request, project: str, workspace: str, nodeId: str | None = None):
        if request.state.actor not in ("human", "agent"):
            return JSONResponse({"error": "Execution identity is required."}, status_code=428)
        try:
            result = await run_in_threadpool(OporaVerifications(canvas).history, project, workspace, nodeId, domain="harness-fixtures")
            return {**result, "quarantine": await run_in_threadpool(quarantine, canvas, project, workspace),
                    "budget": await run_in_threadpool(capacity, canvas, project, workspace)}
        except (ValueError, KeyError, TypeError):
            return JSONResponse({"error": "Verifier history is unavailable in this scope."}, status_code=409)

    async def submit(request, operation):
        if request.state.actor not in ("human", "agent"):
            return JSONResponse({"error": "Execution identity is required."}, status_code=428)
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 4096:
                return JSONResponse({"error": "Verifier request exceeds 4096 bytes."}, status_code=413)
            body.extend(chunk)
        try:
            return await run_in_threadpool(operation, strict_json(bytes(body)))
        except (ValueError, KeyError, TypeError):
            return JSONResponse({"error": "Verifier request is unavailable, conflicting or unauthorized."}, status_code=409)

    @router.post("/requests")
    async def verify(request: Request):
        return await submit(request, verifier.verify)

    @router.post("/eligibility")
    async def eligibility(request: Request):
        return await submit(request, HarnessStability(canvas).assess)

    @router.post("/eligibility/retained")
    async def retained_eligibility(request: Request):
        return await submit(request, RetainedStability(canvas).assess)

    @router.post("/eligibility/shared")
    async def shared_eligibility(request: Request):
        return await submit(request, SharedEligibility(canvas).assess)

    return router
