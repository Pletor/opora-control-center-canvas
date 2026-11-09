"""Typed research provenance and complete native readback for the first unaccepted draft."""
from copy import deepcopy

from backend.canvas.graph import digest
from backend.canvas.payload_errors import NextStep
from backend.canvas.research_plan_source import validate_source
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State, fill_defaults
from database.repositories.opora_changesets import ChangesetRepository


def prepare(service, project, workspace, source):
    validate_source(service, project, workspace, source)
    if ChangesetRepository(service.db_for(project), project, workspace).head() is not None:
        raise ValueError("Research canvas draft requires no accepted head; use a pending graph proposal.")
    return {"researchSource": deepcopy(source), "acceptedHeadAtWrite": None}


def evidence(service, project, workspace, built, wid_of, saved, revision, before_graph, before_state):
    documents = []
    for kind, values, revisions in (("spec", built.specs, built.spec_revisions),
                                   ("text", built.texts, built.text_revisions)):
        for node in sorted(values):
            documents.append({"nodeId": node, "kind": kind, "ownerWorkspace": wid_of(node),
                              "revision": revisions.get(node, 0) + 1, "contentDigest": digest(values[node])})
    affected = {node["id"] for node in built.nodes} | set(built.specs) | set(built.texts)
    for node in set(before_state["nodes"]) | set(built.state["nodes"]):
        if before_state["nodes"].get(node) != built.state["nodes"].get(node):
            affected.add(node)
    prior_nodes = {node["id"]: node for node in before_graph["nodes"]}
    for node in built.new_graph()["nodes"]:
        meaningful = lambda value: {key: item for key, item in value.items() if key not in ("x", "y")}
        if meaningful(node) != meaningful(prior_nodes.get(node["id"], {})):
            affected.add(node["id"])
    prior_edges = {edge["id"]: edge for edge in before_graph["edges"]}
    after_edges = {edge["id"]: edge for edge in built.new_graph()["edges"]}
    for edge_id in prior_edges.keys() | after_edges.keys():
        if prior_edges.get(edge_id) != after_edges.get(edge_id):
            for edge in (prior_edges.get(edge_id), after_edges.get(edge_id)):
                if edge:
                    affected.update((edge["source"], edge["target"]))
    return {"digest": saved["digest"], "revision": revision, "affectedNodeIds": sorted(affected),
            "stateDigest": digest(fill_defaults(deepcopy(built.state))),
            "nodeIds": sorted(node["id"] for node in built.nodes), "edgeIds": sorted(edge["id"] for edge in built.edges),
            "documents": documents}


def verify(service, project, workspace, response):
    """Called on a trusted immutable operation receipt, never on a model's success assertion."""
    with service.graph_lock_for(project), service.lock_for(project):
        validate_source(service, project, workspace, response["researchSource"])
        expected = response["canvasDraft"]
        current = service.view(project, workspace)
        state = DesktopV3State(service).current(project, workspace)
        valid = (response.get("acceptedHeadAtWrite", "missing") is None
                 and current["digest"] == expected["digest"] and state["revision"] == expected["revision"]
                 and digest(state["state"]) == expected["stateDigest"])
        for document in expected["documents"]:
            store = service.specs if document["kind"] == "spec" else service.texts
            field = "fields" if document["kind"] == "spec" else "text"
            stored = store.read((project, document["ownerWorkspace"], document["nodeId"]))
            valid = valid and stored["revision"] == document["revision"] and digest(stored[field]) == document["contentDigest"]
        if not valid:
            raise NextStep("Saved research draft no longer matches native stores.", code="draft_readback_conflict",
                           hint="Reconcile the saved draft before continuing; do not create a duplicate.")
        return {**deepcopy(expected), "acceptedHeadAtReadback":
                ChangesetRepository(service.db_for(project), project, workspace).head()}
