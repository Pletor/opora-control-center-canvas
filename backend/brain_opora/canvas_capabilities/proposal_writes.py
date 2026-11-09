"""Shared content edits become native immutable proposals, never live writes."""
from backend.canvas.opora_graph_proposals import OporaGraphProposals
from backend.canvas.opora_graph_change_plan import heart_scope
from backend.canvas.payload_errors import NextStep
from backend.brain_opora.canvas_capabilities.contracts import contract

BASE = ("parentRevision", "expectedGraphDigest", "subject")
OPTIONS = dict(effect="proposal", output="Persisted native proposal; human review required; live content unchanged",
               cas="caller acceptedHead, graphDigest and document/state revisions", replay=True)
CONTRACTS = {
    "canvas_routes.canvas_plan": contract((*BASE, "plan"), ("researchSource",), **{**OPTIONS,
        "effect": "draft-or-proposal", "output": "No accepted baseline: verified native working draft; otherwise pending proposal. subject labels proposals only."}),
    "node_routes.save_node_text": contract((*BASE, "node", "expectedStateRevision", "expectedRevision", "text"), **OPTIONS),
    "node_routes.save_node_spec": contract((*BASE, "node", "expectedStateRevision", "expectedRevision", "fields"), **OPTIONS),
}


def persist(service, project, workspace, session, data, request_id):
    heart_scope(data["plan"])
    native = OporaGraphProposals(service)
    result = native.create({**data, "project": project, "workspace": workspace, "operationId": request_id},
                           {"kind": "agent", "name": session["worker_name"]})
    saved = native.read(project, workspace, result["id"])
    derived = {'accepted', 'supersededBy', 'latestProposalId'}
    if {k: v for k, v in saved.items() if k not in derived} != {k: v for k, v in result.items() if k not in derived}:
        raise NextStep("Persisted proposal differs from the returned content.", code="capability_readback_failed",
                       hint="Read the existing proposal; do not retry with a new requestId.")
    return {"state": "persisted", "verified": True, "accepted": result["accepted"], "result": result}


def prepare(service, project, workspace, session, capability, data, request_id):
    body = {key: data[key] for key in BASE}
    if capability == "canvas_routes.canvas_plan":
        if data["parentRevision"] is None:
            return initial(service, project, workspace, session, data, request_id)
        body["plan"] = data["plan"]
        if "researchSource" in data:
            body["plan"] = {**body["plan"], "researchSource": data["researchSource"]}
    else:
        field = "text" if capability == "node_routes.save_node_text" else "spec"
        value_key = "text" if field == "text" else "fields"
        body["plan"] = {"draftVersion": 3, "extend": [{"node": "@" + data["node"],
            "expectedRevision": data["expectedStateRevision"],
            field: {"expectedRevision": data["expectedRevision"], value_key: data[value_key]}}]}
    return persist(service, project, workspace, session, body, request_id)


def initial(service, project, workspace, session, data, request_id):
    """No accepted baseline: native working draft, with native receipts before stale checks."""
    from backend.canvas.canvas_plan import apply_plan
    from backend.canvas.operation_receipts import Receipt
    payload = {"project": project, "workspace": workspace, "digest": data["expectedGraphDigest"],
               "plan": data["plan"], "operationId": request_id}
    if "researchSource" in data:
        payload["researchSource"] = data["researchSource"]
    author = {"kind": "agent", "name": session["worker_name"]}
    with service.graph_lock_for(project):
        with service.lock_for(project):
            replay = Receipt(payload, "canvas-plan", author).replay(service.db_for(project))
        if replay is None:
            if OporaGraphProposals(service).context(project, workspace)["acceptedHead"] is not None:
                raise NextStep("Accepted baseline now exists; prepare a native proposal using its context.",
                               code="capability_context_changed", hint="Read current context without changing an existing operation request.")
            replay = apply_plan(service, payload, actor="agent", operation_actor=author)
        return {"state": "persisted", "kind": "working-draft", "verified": True,
                "accepted": False, "result": replay}
