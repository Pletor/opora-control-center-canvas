"""Existing initial draft correction uses native CAS, two receipts and authoritative reads."""
from copy import deepcopy

from backend.api.brain_opora.test_canvas_capability_routes import setup, call, SCOPE


def test_initial_draft_grounding_preserves_identity_source_and_rejects_stale_scope(setup):
    client, service, auth = setup

    def read(capability, data=None):
        response = call(client, auth, capability, data)
        assert response.status_code == 200, response.text
        return response.json()["result"]

    context = read("opora_graph_routes.context")
    source = "Original question: unverified; no sources."
    step = {"id": "s1", "order": 1, "title": "Locate source", "kind": "research",
            "files": ["src/cache/"], "dependsOn": [], "acceptance": ["Record source revision"]}
    initial = {"parentRevision": None, "expectedGraphDigest": context["graphDigest"], "subject": "Fixture",
               "plan": {"nodes": [{"ref": "verify", "kind": "node", "name": "Verify tenant isolation",
                   "purpose": source, "card": {"status": "ready"},
                   "spec": {"goal": "Two tenants, same query", "steps": [step]}}]}}
    created = call(client, auth, "canvas_routes.canvas_plan", initial, "seed-grounding")
    assert created.status_code == 200, created.text
    node = created.json()["result"]["refs"]["verify"]
    original = read("node_routes.node_spec", {"node": node})
    context = read("opora_graph_routes.context")
    fields = deepcopy(original["fields"])
    fields["steps"][0]["files"] = []
    fields["non_goals"] = "Source must first be made available; no implementation or acceptance."
    update = {"parentRevision": None, "expectedGraphDigest": context["graphDigest"], "subject": "Grounding",
              "plan": {"extend": [{"node": "@" + node, "expectedRevision": context["stateRevision"],
                                     "spec": {"expectedRevision": original["revision"], "fields": fields}}]}}
    for scope in ({**SCOPE, "project": "foreign"}, {**SCOPE, "workspace": "main"}):
        assert call(client, auth, "canvas_routes.canvas_plan", update, "foreign", scope).status_code == 403
    changed = call(client, auth, "canvas_routes.canvas_plan", update, "ground-spec")
    assert changed.status_code == 200, changed.text
    assert call(client, auth, "canvas_routes.canvas_plan", update, "ground-spec").json() == changed.json()
    assert call(client, auth, "canvas_routes.canvas_plan", update, "stale-spec").status_code == 409
    assert read("node_routes.node_spec", {"node": node})["fields"] == fields
    view = read("canvas_routes.view")
    graph = deepcopy(view["graph"])
    graph["nodes"][0]["card"]["status"] = "draft"
    body = {"graph": graph, "digest": view["digest"], "expectedAcceptedHead": None}
    changed_graph = call(client, auth, "canvas_routes.graph", body, "ground-status")
    assert changed_graph.status_code == 200, changed_graph.text
    assert call(client, auth, "canvas_routes.graph", body, "ground-status").json() == changed_graph.json()
    assert call(client, auth, "canvas_routes.graph", body, "stale-status").status_code == 409
    assert call(client, auth, "canvas_routes.graph", body, "foreign-status", {**SCOPE, "workspace": "main"}).status_code == 403
    actual = read("canvas_routes.view")["graph"]
    assert actual == graph and len(actual["nodes"]) == 1
    assert actual["nodes"][0]["id"] == node and actual["nodes"][0]["purpose"] == source
    assert read("opora_graph_routes.context")["acceptedHead"] is None
    assert read("node_routes.node_spec", {"node": node})["fields"] == fields
