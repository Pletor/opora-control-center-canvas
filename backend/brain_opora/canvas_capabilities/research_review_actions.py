"""The review capability prepares a native human decision; it never impersonates the reviewer."""
from urllib.parse import urlencode

from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.editor.research import model, review_proposals

CONTRACTS = {
    "research_decision_routes.review": contract(("review",), effect="proposal", replay=True,
        output="Native pinned review preparation displayed in ResearchDecision; human review is still pending",
        cas="Exact immutable source preimages and review digest; human acceptance transaction only"),
}
PREFIX = "research_review_proposal_routes."
CONTRACTS.update({
    PREFIX + "prepare": CONTRACTS["research_decision_routes.review"].copy(),
    PREFIX + "listing": contract(("decisionId",)),
    PREFIX + "read": contract(("identifier",)),
    PREFIX + "decide": contract(("identifier", "digest", "action"), effect="human-decision",
        cas="Exact immutable proposal digest; actual human action revalidates all native source preimages",
        output="Exact pending record and scoped review URL; accept/reject still requires human UI"),
})
for specification in CONTRACTS.values():
    specification["test"] = "backend/api/editor/test_research_review_proposals.py"


def invoke(service, project, workspace, session, capability, data, request_id):
    action = capability.removeprefix(PREFIX)
    if action == "listing":
        return {"state": "read", "result": review_proposals.listing(service, project, workspace, data["decisionId"])}
    if action in ("read", "decide"):
        result = review_proposals.read(service, project, workspace, data["identifier"])
        if action == "read":
            return {"state": "read", "result": result}
        if data["action"] not in ("accept", "reject"):
            model.fail("Review action must be accept or reject.")
        if data["digest"] != result["digest"]:
            model.fail("Review digest differs from the immutable proposal.", 409, "research_review_proposal_stale")
        if result["status"] != "pending":
            model.fail("Review already has a human decision; read its native result.", 409, "research_review_proposal_decided")
        query = {"screen": "canvas", "mode": "research", "project": project, "workspace": workspace,
                 "researchCard": result["snapshot"]["decision"]["id"], "researchReview": result["id"],
                 "researchDigest": result["digest"]}
        return {"state": "awaiting_human", "verified": True, "requestedAction": data["action"],
                "reviewUrl": "/?" + urlencode(query), "result": result}
    result = review_proposals.prepare(service, project, workspace, data["review"], request_id, "agent", session["worker_name"])
    return {"state": "proposal", "verified": True, "result": result}
