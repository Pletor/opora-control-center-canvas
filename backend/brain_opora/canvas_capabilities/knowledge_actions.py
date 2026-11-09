"""Canonical research through the authenticated Heart's existing scope only."""
from backend.brain_opora.canvas_capabilities.contracts import contract
from backend.brain_opora.canvas_capabilities.native_journal import run
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.editor.research import knowledge, model

CONTRACTS = {
    "research_knowledge_routes.context": contract((), ("scopeNodeId",)),
    "research_knowledge_routes.search": contract(("scopes", "query"),
        ("kinds", "verification", "limit", "resultType", "ranking"),
        types={"scopes": "json", "kinds": "json", "verification": "json"}),
    "research_knowledge_routes.bind": contract(("scopeNodeId", "source", "expectedRevision", "archived"),
        effect="research", replay=True, cas="Native binding expectedRevision and exact canonical source revision"),
}


def invoke(service, project, workspace, session, capability, data, request_id):
    def authorize(p, w, write=False):
        if (p, w) != (project, workspace):
            raise GateError(403, "gate_scope", "Canonical source is outside this Heart session.",
                            "Use an explicitly authorized source session; a binding is not a grant.")
    operation = capability.rsplit(".", 1)[1]
    if operation == "context":
        return {"state": "read", "result": {**knowledge.context(service, project, workspace,
            data.get("scopeNodeId", ""), authorize), "workspace": workspace}}
    if operation == "search":
        kind = data.get("resultType", "research")
        if kind not in ("research", "solution"):
            model.fail("Unknown search result type.")
        if kind == "solution":
            if data.get("kinds") or data.get("verification"):
                model.fail("Research filters require research results.")
            result = knowledge.solutions(service, data["scopes"], data["query"], data.get("limit", 30),
                authorize, data.get("ranking", "hybrid"))
        else:
            if "ranking" in data:
                model.fail("Ranking requires solution results.")
            result = knowledge.search(service, data["scopes"], data["query"], data.get("kinds", []),
                data.get("verification", []), data.get("limit", 30), authorize)
        return {"state": "read", "result": result}
    source = knowledge.reference(data["source"])
    authorize(source["projectId"], source["workspaceId"])
    def verify(before, after, result):
        if result not in after:
            raise ValueError("Binding native readback differs.")
    return run(service, project, workspace, session, capability, data, request_id,
        snapshot=lambda: knowledge._bindings(service, project, workspace),
        action=lambda: knowledge.bind(service, project, workspace, data["scopeNodeId"], source,
            data["expectedRevision"], data["archived"], authorize, session["worker_name"]), verify=verify)
