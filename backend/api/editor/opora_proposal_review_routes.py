"""Scoped review discussions and human acceptance policy use the same API as the UI."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.canvas.authority import can_act
from backend.canvas.opora_proposal_review_service import ProposalReviews


def create_proposal_review_router(canvas):
    router = APIRouter(prefix="/api/oporahub/proposal-reviews", tags=["oporahub"])
    reviews = ProposalReviews(canvas)

    def call(request, action):
        if request.state.actor not in {"human", "agent"}:
            return JSONResponse({"error": "Proposal review identity is required.", "code": "identity_required"}, status_code=428)
        by = {"kind": request.state.actor, "name": request.state.agent if request.state.actor == "agent" else "Human"}
        try:
            return action(by)
        except (ValueError, TypeError) as error:
            return JSONResponse({"error": str(error), "code": "proposal_review_conflict"}, status_code=409)

    @router.get("/policy")
    def policy(project: str, workspace: str, request: Request):
        def read(by):
            value = reviews.policy(project, workspace)
            return {**value, "canConfigure": can_act(by["kind"]) and not value["readOnly"]}
        return call(request, read)

    @router.post("/policy")
    def configure(payload: dict, request: Request):
        return call(request, lambda by: reviews.configure(payload, by))

    @router.post("/policy/disable")
    def disable(payload: dict, request: Request):
        def apply(by):
            if set(payload) != {"project", "workspace", "expectedPolicyHead"}:
                raise ValueError("Invalid acceptance policy disable fields.")
            current = reviews.policy(payload["project"], payload["workspace"])
            rules = current["policy"]["rules"] if current["policy"] else {"requireAcknowledgementFrom": "none", "blockOpenFindings": False}
            return reviews.configure({**payload, "enabled": False, "rules": rules}, by)
        return call(request, apply)

    @router.get("/receipts/{revision}")
    def receipt(revision: str, project: str, workspace: str, request: Request):
        return call(request, lambda _: reviews.receipt(project, workspace, revision))

    @router.get("")
    def context(project: str, workspace: str, proposalKind: str, proposalId: str, request: Request):
        def read(by):
            value = reviews.context(project, workspace, proposalKind, proposalId)
            human = can_act(by["kind"]) and not value["readOnly"]
            can_ack = human and bool(value["policy"] and value["policy"]["enabled"])
            can_ack = can_ack and value["parentAcceptedHead"] == value["acceptedHead"] and value["acceptedRevision"] is None
            return {**value, "canAccept": can_act(by["kind"]) and value["eligible"], "canAcknowledge": can_ack,
                    "canResolve": human, "canComment": not value["readOnly"]}
        return call(request, read)

    @router.post("/events")
    def event(payload: dict, request: Request):
        return call(request, lambda by: reviews.append(payload, by))

    return router
