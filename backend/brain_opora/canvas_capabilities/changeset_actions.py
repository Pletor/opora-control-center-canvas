"""Native immutable specification proposals; shared accepted authority remains untouched."""
from backend.canvas.opora_changesets import OporaChangesets
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.payload_errors import NextStep
from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.brain_opora.canvas_capabilities.native_journal import run

PREFIX = "opora_changeset_routes."
CONTRACTS = {
    "opora_graph_routes.rebase": contract(("identifier", "expectedAcceptedHead", "expectedGraphDigest"),
        effect="proposal", replay=True, cas="native accepted head, graph digest and full pinned content"),
    PREFIX + "context": contract(),
    PREFIX + "history": contract(),
    PREFIX + "read": contract(("identifier",)),
    PREFIX + "revision": contract(("identifier",)),
    PREFIX + "propose": contract(("parentRevision", "expectedGraphDigest", "subject", "changes"),
        effect="proposal", replay=True, cas="native accepted head, graph digest and document revisions"),
    PREFIX + "rebase": contract(("identifier", "expectedAcceptedHead"), effect="proposal", replay=True,
        cas="native accepted head and unchanged affected documents"),
}


for _contract in CONTRACTS.values():
    _contract["test"] = "backend/api/brain_opora/test_canvas_capability_changesets.py"


def invoke(service, project, workspace, session, capability, data, request_id):
    native = OporaGraphProposals(service) if capability == "opora_graph_routes.rebase" else OporaChangesets(service)
    action = "rebase" if capability == "opora_graph_routes.rebase" else capability.removeprefix(PREFIX)
    if action == "context":
        return {"state": "read", "result": native.context(project, workspace)}
    if action == "history":
        return {"state": "read", "result": native.list(project, workspace)}
    if action == "read":
        return {"state": "read", "result": native.read(project, workspace, data["identifier"])}
    if action == "revision":
        return {"state": "read", "result": native.revision(project, workspace, data["identifier"])}
    payload = {"project": project, "workspace": workspace, **{k: v for k, v in data.items() if k != "identifier"}}
    author = {"kind": "agent", "name": session["worker_name"]}

    def snapshot():
        return {"context": native.context(project, workspace), "history": native.list(project, workspace)}

    def verify(before, after, result):
        if (before["context"] != after["context"] or result.get("accepted") is not False
                or native.read(project, workspace, result["id"]) != result):
            raise NextStep("Native proposal readback differs or changed working specifications.",
                           code="operation_incomplete", hint="Inspect the stored proposal before continuing.")

    # OP-B171BE.changesets: native validation and immutable proposal store remain authoritative.
    return run(service, project, workspace, session, capability, data, request_id, snapshot=snapshot,
               action=lambda: native.create(payload, author) if action == "propose"
               else native.rebase(data["identifier"], payload, author), verify=verify)
