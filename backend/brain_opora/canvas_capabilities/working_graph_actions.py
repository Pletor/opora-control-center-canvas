"""Faithful native graph candidates and recovery-aware working operations."""
from urllib.parse import urlencode

from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.canvas.opora_graph_candidate import create
from backend.editor.node.removal_reviews import prepare, read

CONTRACTS = {
    "canvas_routes.graph": contract(("graph", "digest", "expectedAcceptedHead"), ("undo", "subject"), effect="proposal", replay=True,
        cas="Exact working graph digest and accepted head; accepted scope produces full native graph-only proposal"),
    "canvas_routes.remove_item": contract(("kind", "target", "digest", "confirmed"), effect="proposal", replay=True,
        cas="Native removal preview plus pinned graph/state/workspace preimage; protected or accepted scope requires human review"),
    "canvas_routes.restore_removed": contract(("recoveryId", "digest"), effect="proposal", replay=True,
        cas="Native scoped one-use recovery and exact graph/state/workspace preimage"),
    "working_review_routes.read": contract(("operation", "identifier"), output="Exact scoped immutable preparation and separate native application status"),
    "working_review_routes.apply": contract(("operation", "identifier"), effect="human-decision", output="Stored scoped review URL; never applies a human decision"),
}
for item in CONTRACTS.values():
    item["test"] = "backend/api/brain_opora/test_canvas_capability_working_graph.py"


def invoke(service, project, workspace, session, capability, data, request_id):
    operation = capability.split(".")[1]
    if capability.startswith("working_review_routes."):
        saved = read(service, project, workspace, data["operation"], data["identifier"])
        if operation == "read":
            return {"state": "read", "result": saved}
        if saved["status"] != "complete" or saved["preparation"].get("state") != "awaiting_human" or saved["application"]:
            raise ValueError("This operation is not awaiting a human decision.")
        return saved["preparation"]
    author = {"kind": "agent", "name": session["worker_name"]}
    if operation != "graph":
        return prepare(service, project, workspace, operation, data, request_id, author)
    # The caller's accepted-head observation determines the request kind, so lost-response
    # replay remains the same operation even if another acceptance has since advanced.
    if data["expectedAcceptedHead"] is not None:
        item = create(service, {"project": project, "workspace": workspace, "graph": data["graph"],
            "expectedGraphDigest": data["digest"], "parentRevision": data["expectedAcceptedHead"],
            "subject": data.get("subject", "Kontrola úplného grafu"), "undo": data.get("undo", False), "operationId": request_id}, author)
        query = urlencode({"project": project, "workspace": workspace, "screen": "canvas", "environment": "hub", "ohGraph": item["id"]})
        return {"state": "awaiting_human", "applied": False, "proposal": item, "url": "/?" + query}
    with service.graph_lock_for(project), service.lock_for(project):
        # prepare replays before observing authority; new requests refuse newly accepted scopes.
        return prepare(service, project, workspace, operation,
            {"graph": data["graph"], "digest": data["digest"], "undo": data.get("undo", False)}, request_id, author)
