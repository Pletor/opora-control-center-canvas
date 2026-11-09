"""Native research batches and immutable human review reads; never manufactured approval."""
from backend.editor.research import service as research, decisions, decision_tasks
from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.canvas.payload_errors import NextStep

CONTRACTS = {
    "research_routes.apply": contract(("operations",), ("continuation",), effect="research",
        cas="native expectedRevision per entity", replay=True, output="Native atomic batch with full historical readback"),
    "research_decision_routes.listing": contract(("decisionId",)),
    "research_decision_routes.read": contract(("id",)),
    "research_decision_routes.task_status": contract(("id",)),
}


for _contract in CONTRACTS.values():
    _contract["test"] = "backend/api/brain_opora/test_canvas_capability_research.py"


def invoke(service, project, workspace, session, capability, data, request_id):
    if capability == "research_decision_routes.listing":
        return {"state": "read", "result": decisions.listing(service, project, workspace, data["decisionId"])}
    if capability == "research_decision_routes.read":
        return {"state": "read", "result": decisions.read(service, project, workspace, data["id"])}
    if capability == "research_decision_routes.task_status":
        return {"state": "read", "result": decision_tasks.status(service, project, workspace, data["id"])}
    # OP-B171BE.research: native batch receipt is the authority; no second research store or approvals.
    result = research.apply(service, {"project": project, "workspace": workspace, "key": request_id, **data},
                            "agent", session["worker_name"])
    for kind, reader in (("cards", research.detail), ("edges", research.edge_detail)):
        for item in result[kind]:
            actual = reader(service, project, workspace, item["id"], item["revision"])[kind[:-1]]
            if actual != item:
                raise NextStep("Native research revision differs from its receipt.", code="capability_readback_failed",
                               hint="Read the existing pinned revision; do not repeat with another requestId.")
    return {"state": "persisted", "verified": True, "result": result}
