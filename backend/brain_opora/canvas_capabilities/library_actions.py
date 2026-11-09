"""Finite native library writes or durable actionable human review."""
from urllib.parse import urlencode

from fastapi import HTTPException
from pydantic import ValidationError

from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.flow import library_reviews
from backend.flow.graph_check import FlowInvalid
from backend.flow.workflows import FlowConflict, FlowNotFound

CONTRACTS = {
    "library_review_routes.reviews": contract(output="Scoped native Library reviews"),
    "library_review_routes.review": contract(("identifier",), output="Scoped native Library review"),
    "library_review_routes.decide": contract(("identifier", "action"), effect="human-decision", output="Actual human review UI; never an agent acceptance"),
    "library_routes.folder_create": contract(("owner", "slug", "title"), ("description", "order"), effect="draft", replay=True),
    "library_routes.folder_update": contract(("folder_id", "expectedFolderDigest"), ("title", "description", "order"), effect="draft", replay=True),
    "library_routes.folder_delete": contract(("folder_id", "expectedFolderDigest"), effect="draft", replay=True),
    "library_routes.flow_create": contract(("folder", "slug", "title"), ("description",), effect="draft", replay=True),
    "library_routes.flow_adopt": contract(("workflow_id",), ("nodeId",), effect="draft", replay=True),
    "library_routes.flow_contribute": contract(("workflow_id", "folder", "slug", "title"), ("description",), effect="draft", replay=True),
    "library_routes.flow_promote": contract(("workflow_id",), ("folder",), effect="draft", replay=True),
}
for _contract in CONTRACTS.values():
    _contract.update(test="backend/api/brain_opora/test_canvas_capability_library_actions.py",
                     output="Native agent-owned mutation or persisted human review with actual review UI", cas="native scoped preimage at human acceptance")


def invoke(service, project, workspace, session, capability, data, request_id):
    try:
        if capability.startswith("library_review_routes."):
            with service.registry_lock:
                if capability.endswith(".reviews"):
                    return {"state": "read", "result": library_reviews.listing(service, project, workspace)}
                result = library_reviews.read(service, project, workspace, data["identifier"])
                if capability.endswith(".review"):
                    return {"state": "read", "result": result}
                if data["action"] not in ("accept", "reject"):
                    raise FlowInvalid("Review decision is accept or reject.")
                if result["status"] != "pending":
                    return {"state": result["status"], "applied": result["status"] in ("accepted", "applied"),
                            "result": result, "url": review_url(project, workspace, result["id"])}
                return {"state": "awaiting_human", "applied": False, "result": result, "url": review_url(project, workspace, result["id"])}
        result = library_reviews.submit(service, project, workspace, {"kind": "agent", "name": session["worker_name"]},
                                         capability.split(".")[1], data, request_id)
        human = result["requiresHuman"]
        return {"state": "awaiting_human" if human and result["status"] == "pending" else result["status"],
                "applied": result["status"] in ("accepted", "applied"), "verified": True, "result": result,
                "url": review_url(project, workspace, result["id"])}
    except ValidationError as error:
        raise HTTPException(422, error.errors(include_url=False, include_context=False)) from error
    except FlowNotFound as error:
        raise HTTPException(404, str(error)) from error
    except FlowConflict as error:
        raise HTTPException(409, str(error)) from error
    except FlowInvalid as error:
        raise HTTPException(422, str(error)) from error


def review_url(project, workspace, identifier):
    return "/?" + urlencode({"project": project, "workspace": workspace, "screen": "canvas",
                              "environment": "project", "projectView": "library", "libraryReview": identifier})
