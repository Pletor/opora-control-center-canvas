"""Existing immutable content proposals; native authority decides acceptance."""
from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.brain_opora.canvas_capabilities.native_journal import run
from backend.canvas.opora_content_changes import OporaContentChanges
from backend.canvas.opora_content_acceptance import OporaContentAcceptance

CONTRACTS = {
    "opora_content_routes.listing": contract(),
    "opora_content_routes.detail": contract(("identifier",)),
    "opora_content_routes.create": contract(("expectedAcceptedHead", "subject", "changes"),
        effect="proposal", replay=True, cas="Native accepted head and observed content revisions"),
    "opora_content_routes.accept": contract(("identifier", "expectedAcceptedHead", "reviewedProposalId", "adoptBaseContentDigest"),
        effect="acceptance", replay=True, cas="Native reviewed proposal, accepted head, content CAS and runtime authority"),
}


def invoke(service, project, workspace, session, capability, data, request_id):
    native = OporaContentChanges(service)
    operation = capability.rsplit(".", 1)[1]
    if operation == "listing":
        return {"state": "read", "result": native.list(project, workspace)}
    if operation == "detail":
        return {"state": "read", "result": native.read(project, workspace, data["identifier"])}
    by = {"kind": "agent", "name": session["worker_name"]}
    def action():
        payload = {"project": project, "workspace": workspace, **data}
        if operation == "create":
            return native.create(payload, by)
        identifier = payload.pop("identifier")
        return OporaContentAcceptance(service).accept(identifier, payload, by)
    def verify(before, after, result):
        if operation == "create":
            valid = native.read(project, workspace, result["id"])["proposal"] == result
        else:
            valid = native.read(project, workspace, data["identifier"])["accepted"] == result["id"]
        if not valid:
            raise ValueError("Content native readback differs.")
    return run(service, project, workspace, session, capability, data, request_id,
        snapshot=lambda: native.list(project, workspace), action=action, verify=verify,
        allow_head_change=operation == "accept")
