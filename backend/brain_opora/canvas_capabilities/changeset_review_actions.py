"""Exact native specification review targets; no agent acceptance."""
from urllib.parse import urlencode

from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.canvas import opora_baseline_preparations
from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.payload_errors import NextStep

CONTRACTS = {
    "opora_changeset_routes.baseline_preparation": contract(("identifier",), output="Exact immutable scoped baseline preparation receipt"),
    "opora_changeset_routes.baseline": contract(
        ("expectedAcceptedHead", "expectedGraphDigest", "expectedSpecificationsVersion", "subject"),
        effect="proposal", replay=True, cas="Null accepted head, exact graph digest and specification version",
        output="Durable exact baseline preparation for human UI; no accepted revision"),
    "opora_changeset_routes.accept": contract(("identifier", "expectedAcceptedHead"), effect="human-decision",
        cas="Exact current parent; native acceptance independently revalidates review and document preconditions",
        output="Existing immutable changeset and actual scoped review URL; never automatic acceptance"),
}
for value in CONTRACTS.values():
    value["test"] = "backend/api/brain_opora/test_canvas_capability_changeset_review.py"


def invoke(service, project, workspace, session, capability, data, request_id):
    if capability.endswith(".baseline_preparation"):
        return {"state": "read", "result": opora_baseline_preparations.read(service, project, workspace, data["identifier"])}
    if capability.endswith(".baseline"):
        return opora_baseline_preparations.prepare(service, project, workspace, session, data, request_id)
    native = OporaChangesets(service)
    with service.graph_lock_for(project), service.lock_for(project):
        proposal = native.read(project, workspace, data["identifier"])
        context = native.context(project, workspace)
        if (proposal["accepted"] or context["readOnly"] or not context["acceptedHead"]
                or context["acceptedHead"] != data["expectedAcceptedHead"]
                or proposal["parentRevision"] != context["acceptedHead"]):
            raise NextStep("Proposal is no longer pending on the requested accepted head.",
                           code="changeset_review_conflict", hint="Read the existing proposal and native context.")
        query = {"screen": "canvas", "environment": "hub", "project": project, "workspace": workspace,
                 "ohChangeset": proposal["id"]}
        return {"state": "awaiting_human", "verified": True, "result": proposal,
                "expectedAcceptedHead": context["acceptedHead"], "reviewUrl": "/?" + urlencode(query)}
