"""Reviewer identities, review metrics, eval set and recurring findings (docs/oporahub-review-identity.md)."""
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from backend.canvas.opora_review_evals import ReviewEvals
from backend.canvas.opora_review_identity import IdentityProofMissing, ReviewIdentities
from backend.canvas.opora_review_insight_common import InsightHumanRequired, InsightMissing
from backend.canvas.opora_review_metrics import read_review_metrics
from backend.canvas.opora_review_recurring import promote, read_recurring
from backend.integrations.github_review_transport import GitHubReadError

SCOPE = {"min_length": 1, "max_length": 64}


def create_review_insight_router(service, identities=None, evals=None):
    router = APIRouter(prefix="/api/oporahub", tags=["oporahub"])
    identities, evals = identities or ReviewIdentities(service), evals or ReviewEvals(service)

    def call(request, action):
        if request.state.actor not in ("human", "agent"):
            return JSONResponse({"error": "Review identity is required.", "code": "identity_required"}, status_code=428)
        try:
            return action()
        except InsightHumanRequired as exc:
            return JSONResponse({"error": str(exc), "code": "human_required"}, status_code=403)
        except InsightMissing as exc:
            return JSONResponse({"error": str(exc), "code": "not_found"}, status_code=404)
        except IdentityProofMissing as exc:
            return JSONResponse({"error": str(exc), "code": "identity_proof_missing"}, status_code=409)
        except GitHubReadError:
            return JSONResponse({"error": "GitHub is unavailable.", "code": "github_unavailable"}, status_code=502)
        except ValueError as exc:
            return JSONResponse({"error": str(exc), "code": "review_conflict"}, status_code=409)

    def actor(request):
        return "human" if request.state.actor == "human" else "agent:" + str(getattr(request.state, "agent", ""))

    @router.get("/review-identities")
    def identity_list(request: Request, project: str = Query(**SCOPE)):
        return call(request, lambda: identities.list(project, request.state.actor))

    @router.post("/review-identities/claim")
    def identity_claim(payload: dict, request: Request):
        return call(request, lambda: identities.claim(payload, request.state.actor))

    @router.post("/review-identities/{identity}/verify")
    def identity_verify(identity: str, payload: dict, request: Request):
        return call(request, lambda: identities.verify(identity, payload, request.state.actor))

    @router.post("/review-identities/{identity}/revoke")
    def identity_revoke(identity: str, payload: dict, request: Request):
        return call(request, lambda: identities.revoke(identity, payload, request.state.actor))

    @router.get("/review-metrics")
    def metrics(request: Request, project: str = Query(**SCOPE), workspace: str | None = Query(None, **SCOPE),
                window: str = Query("30d", max_length=8)):
        return call(request, lambda: read_review_metrics(service, project, workspace, window))

    @router.get("/review-evals")
    def eval_list(request: Request, project: str = Query(**SCOPE), workspace: str | None = Query(None, **SCOPE)):
        return call(request, lambda: evals.list(project, workspace))

    @router.get("/review-evals/export.jsonl")
    def eval_export(request: Request, project: str = Query(**SCOPE), workspace: str | None = Query(None, **SCOPE)):
        return call(request, lambda: PlainTextResponse(evals.export_jsonl(project, workspace),
                                                       media_type="application/x-ndjson"))

    @router.post("/review-evals/sync")
    def eval_sync(payload: dict, request: Request):
        return call(request, lambda: evals.sync_reverts(payload))

    @router.post("/review-incidents")
    def incident(payload: dict, request: Request):
        return call(request, lambda: evals.link_incident(payload, actor(request)))

    @router.get("/review-recurring")
    def recurring(request: Request, project: str = Query(**SCOPE)):
        return call(request, lambda: read_recurring(service, project))

    @router.post("/review-recurring/promote")
    def recurring_promote(payload: dict, request: Request):
        return call(request, lambda: promote(service, payload, actor(request)))

    return router
