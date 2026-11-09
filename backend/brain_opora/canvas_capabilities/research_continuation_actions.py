"""Discoverable original research bridge; native source pins and batch identity remain authoritative."""
from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.canvas.payload_errors import NextStep
from backend.editor.research import continuations, originals, model, service as research

CONTRACTS = {
    "research_continuation_routes.listing": contract(output="Scoped native continuation receipts"),
    "research_continuation_routes.original": contract(("identifier",), ("revision",), types={"revision": "integer"},
        output="Original fragment, complete native history, source/details revisions and mapped cards"),
    "research_continuation_routes.materialize": contract(("identifier", "revision", "detailsRevision"), effect="research",
        cas="Exact current source/details revisions; native stable batch key from scope and pins, no requestId",
        output="Native idempotent research batch with complete pinned revision readback"),
}
for _contract in CONTRACTS.values():
    _contract["test"] = "backend/api/brain_opora/test_canvas_capability_research_continuations.py"


def invoke(service, project, workspace, session, capability, data, request_id):
    if capability.endswith(".listing"):
        return {"state": "read", "result": {"project": project, "workspace": workspace,
                "continuations": continuations.listing(service, project, workspace)}}
    if capability.endswith(".original"):
        return {"state": "read", "result": originals.read(service, project, workspace,
                data["identifier"], data.get("revision"))}
    if type(data["revision"]) is not int or data["revision"] < 1:
        model.fail("revision must be a positive integer.")
    if type(data["detailsRevision"]) is not int or data["detailsRevision"] < 0:
        model.fail("detailsRevision must be a nonnegative integer.")
    result = originals.materialize(service, project, workspace, data["identifier"], data["revision"],
                                   data["detailsRevision"], "agent", session["worker_name"])
    for kind, reader in (("cards", research.detail), ("edges", research.edge_detail)):
        for item in result[kind]:
            if reader(service, project, workspace, item["id"], item["revision"])[kind[:-1]] != item:
                raise NextStep("Native original materialization differs from its pinned revision.",
                               code="capability_readback_failed", hint="Inspect the existing native batch; do not recreate it.")
    return {"state": "persisted", "verified": True, "result": result}
