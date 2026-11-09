"""Finite native vault operations and exact human review targets."""
from urllib.parse import urlencode

from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.canvas.payload_errors import InvalidPayload, NextStep
from backend.editor.brief_vault import operation_reviews
from backend.editor.brief_vault.operation_review_contracts import inventory

CONTRACTS = {
    "brief_vault_routes.brief_vault_write": contract(("operation",), ("review",), effect="vault", replay=True,
        cas="Native fragment revision/handler prerequisites; exact preimage for human decisions",
        output="Native verified result or durable exact human intent, never automatic product acceptance"),
    "brief_vault_review_routes.read": contract(("identifier",), output="Exact immutable scoped human intent and decision receipt"),
    "brief_vault_review_routes.decide": contract(("identifier", "digest", "action"), effect="human-decision",
        output="Exact pending human UI target; no native mutation"),
}
CONTRACTS["brief_vault_routes.brief_vault_write"]["operations"] = inventory()
for value in CONTRACTS.values():
    value["test"] = "backend/api/brain_opora/test_canvas_capability_brief_operations.py"


def invoke(service, project, workspace, session, capability, data, request_id):
    if capability == "brief_vault_routes.brief_vault_write":
        return operation_reviews.invoke(service, project, workspace, session, data["operation"], request_id,
                                        review=data.get("review", False))
    intent = operation_reviews.read(service, project, workspace, data["identifier"])
    if capability.endswith(".read"):
        return {"state": "read", "result": intent}
    if data["action"] not in ("accept", "reject"):
        raise InvalidPayload("Action must be accept or reject.", field="action")
    if intent["digest"] != data["digest"] or intent["decision"] is not None:
        raise NextStep("Exact vault intent is no longer pending.", code="vault_review_stale",
                       hint="Read the native intent and its decision receipt.")
    query = {"screen": "canvas", "project": project, "workspace": workspace, "vaultReview": intent["id"]}
    return {"state": "awaiting_human", "verified": True, "requestedAction": data["action"],
            "result": intent, "reviewUrl": "/?" + urlencode(query)}
