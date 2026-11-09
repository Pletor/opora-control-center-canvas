"""Resolve blocking inputs against accepted documents and existing execution evidence.

No status flags are written here. A design is never evidence of implementation;
an agent result alone is never evidence of a merge or functional verification.
"""
from copy import deepcopy

from backend.canvas.graph import digest
from backend.canvas.opora_graph_records import combined
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_executions import Executions
from database.repositories.opora_graph_proposals import GraphProposals


def require_inputs(canvas, project, workspace, node, accepted_head, graph, documents):
    nodes = {item["id"]: item for item in graph["nodes"]}
    sources, cursor = set(), node
    while cursor is not None and cursor in nodes and cursor not in sources:
        sources.add(cursor)
        cursor = nodes[cursor].get("parentId")
    edges = [edge for edge in graph["edges"] if edge.get("relation") == "requires" and edge["source"] in sources]
    if not edges:
        return []
    db = canvas.db_for(project)
    accepted = ChangesetRepository(db, project, workspace).read(accepted_head)
    manifest_id = accepted.get("graphManifestId")
    if not manifest_id:
        raise ValueError("Required inputs unresolved: an accepted graph snapshot is required.")
    pinned = combined(GraphProposals(db, project, workspace).read(manifest_id, manifest=True))
    pinned_edges = {edge["id"]: edge for edge in pinned["edges"]}
    by_id = {doc["nodeId"]: doc for doc in documents}
    result = []
    for edge in edges:
        target, descriptor = edge["target"], edge.get("requirement")
        if pinned_edges.get(edge["id"]) != edge or not descriptor:
            raise ValueError(f"Required input {edge['id']} unresolved: accept an explicit readiness and revision.")
        document = by_id.get(target)
        if not document or document["revision"] != descriptor["revision"]:
            raise ValueError(f"Required input {target} is stale or has no accepted specification at revision {descriptor['revision']}.")
        proof = {"edgeId": edge["id"], "sourceNodeId": edge["source"], "nodeId": target, "readiness": descriptor["readiness"],
                 "revision": descriptor["revision"], "documentDigest": digest(document), "acceptedRevision": accepted_head}
        if descriptor["readiness"] != "design":
            proof.update(_implementation(canvas, project, workspace, target, document, accepted_head))
        if descriptor["readiness"] == "verified":
            proof.update(_verification(canvas, project, workspace, target, descriptor, accepted_head, proof))
        result.append(proof)
    return deepcopy(result)


def _implementation(canvas, project, workspace, node, document, accepted_head):
    from backend.canvas.opora_agent_state_pulls import read
    from backend.brain_opora.determinism.milestone_evidence import semantic_compatible

    repo = Executions(canvas.db_for(project), project, workspace)
    links = {link["executionId"]: link for link in read(canvas, project, workspace) or []
             if link.get("cardId") == node and link.get("state") == "merged" and link.get("mergeSha")}
    # Link presentation order is lexical by UUID; execution history is authoritative
    # newest-first, matching the shared verification receipt evaluator.
    for execution in repo.history(node):
        link = links.get(execution["executionId"])
        if link is None:
            continue
        own = next((item for item in execution["assignment"].get("documents", []) if item["nodeId"] == node), None)
        if own == document:
            # Same document revision alone cannot hide a changed input contract
            # elsewhere in this target's accepted execution scope.
            try:
                semantic_compatible(repo.db, project, workspace, execution["acceptedRevision"], [node])
            except ValueError:
                continue
            return {"executionId": link["executionId"], "executionAcceptedRevision": execution["acceptedRevision"], "mergeSha": link["mergeSha"]}
    raise ValueError(f"Required input {node} has no merged implementation of its exact accepted revision.")


def _verification(canvas, project, workspace, node, requirement, accepted_head, implementation):
    from backend.brain_opora.determinism.milestone_evidence import evaluate

    cases = requirement.get("verification")
    if cases is None:
        raise ValueError(f"Required input {node} verification unresolved: accepted positive and negative test references required.")
    evidence = evaluate(canvas.db_for(project), project, workspace, [{"cards": [node], "verification": {
        "nodeId": node, "acceptedRevision": implementation["executionAcceptedRevision"], **cases}}])
    if not evidence["verified"]:
        raise ValueError(f"Required input {node} verification unresolved: {evidence.get('reason', evidence['status'])}")
    if evidence["executionId"] != implementation["executionId"] or evidence["headSha"] != implementation["mergeSha"]:
        raise ValueError(f"Required input {node} verification is not bound to its exact merged implementation.")
    return {"verification": evidence}
