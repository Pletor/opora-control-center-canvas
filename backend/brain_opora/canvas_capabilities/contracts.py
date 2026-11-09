"""Finite implemented contracts; the native domain remains the payload validator."""
def contract(required=(), optional=(), *, effect="read", output="Native response", cas=None, replay=False, types=None):
    return {"required": list(required), "optional": list(optional), "effect": effect,
            "output": output, "cas": cas, "replay": replay, "types": types or {},
            "errors": ["gate_token_invalid", "gate_scope", "invalid_payload", "native_validation"],
            "test": "backend/api/brain_opora/test_canvas_capability_routes.py"}


CONTRACTS = {
    "session_view.read": contract(output="Own sessionId,revision,view,state,reason; applied true only for current revision/view acknowledged by live attached human tab"),
    "session_view.update": contract(("expectedRevision", "view"), effect="session-view", output="Persisted private selection/viewport/filter and optional structureCollapsed (unique sectors,nodes,areas); not_applied until visible UI acknowledgement", cas="session revision", replay=True),
    "canvas_routes.view": contract(output="graph,digest,readOnly; current scoped graph"),
    "canvas_routes.canvas_index": contract(optional=("q", "limit"), output="Native searchable card index"),
    "node_routes.node_text": contract(("node",), output="available,text,revision"),
    "node_routes.node_spec": contract(("node",), output="Native spec including accepted/working plan steps"),
    "opora_graph_routes.context": contract(output="acceptedHead,graphDigest,workingGraph,stateRevision"),
    "opora_graph_routes.history": contract(output="items,acceptedHead"),
    "opora_graph_routes.read": contract(("identifier",), output="Immutable proposal with current accepted flag"),
    "opora_graph_routes.create": contract(("parentRevision", "expectedGraphDigest", "subject", "plan"),
        effect="proposal", output="Verified immutable pending proposal, refs and native ID",
        cas="parentRevision + expectedGraphDigest; native document revisions", replay=True),
    "opora_graph_routes.accept": contract(("identifier",), effect="human-decision",
        output="awaiting_human, existing proposal and review URL; never acceptance"),
}
