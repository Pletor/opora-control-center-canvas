"""Scoped solution proof from native progress; research status never proves operation."""
from backend.brain_opora.determinism.milestone_lineage import _node, input_closure
from backend.canvas.opora_agent_state_progress import attach
from backend.canvas.opora_graph_records import combined
from backend.canvas.opora_content_execution import require_accepted_content
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State
from backend.editor.agent_packet.desktop_v3_packets import memory_for, redact_deep
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_executions import Executions
from database.repositories.opora_graph_proposals import GraphProposals


def _inputs(graph, node):
    _, relevant, edges = input_closure(graph, [node])
    nodes = {item["id"]: {**_node(item), "parentId": item.get("parentId")}
             for item in graph["nodes"] if item["id"] in relevant}
    contracts = {edge["id"]: {key: edge[key] for key in ("source", "target", "relation", "requirement") if key in edge}
                 for edge in edges}
    return relevant, {"nodes": nodes, "contracts": contracts}


def _rules(canvas, project, workspace, execution, relevant, graph):
    """Compare current selected constraints to the immutable native handoff.

    Legacy accepted revisions may have no content manifest. Their original
    assignment remains the authority for rules, including inherited scopes.
    """
    specification = execution["assignment"].get("specification", {})
    snapshots = [specification, *specification.get("affectedScopes", [])]
    snapshots.extend(item.get("scope", {}).get("specification", {})
                     for item in execution["assignment"].get("affectedElements", []))
    cards = {card["nodeId"]: card for snapshot in snapshots for card in snapshot.get("cards", [])}
    stored = DesktopV3State(canvas).read(project, workspace)
    for identifier in relevant:
        original = cards.get(identifier, {}).get("instructions", {}).get("rules", [])
        current = stored["state"]["nodes"].get(identifier, {}).get("rules", [])
        if redact_deep(current) != original:
            raise ValueError("Displayed inherited rules differ from the execution contract.")
    paths = [(item.get("sourceRef") or {}).get("path", "")
             for item in graph["nodes"] if item["id"] in relevant]
    original_rules = {rule["id"]: rule for snapshot in snapshots for rule in snapshot.get("rules", [])}
    before = {"revision": 0, "state": {**stored["state"], "rules": list(original_rules.values())}}
    expected = memory_for(before, sorted(relevant), paths, "")["rules"]
    current = memory_for(stored, sorted(relevant), paths, "")["rules"]
    if sorted(expected, key=lambda rule: rule["id"]) != sorted(current, key=lambda rule: rule["id"]):
        raise ValueError("Displayed scoped rules differ from the execution contract.")


def project(canvas, project, workspace, view, identifiers):
    """Caller authorizes this exact project/workspace before invoking; never reads foreign origins."""
    unknown = {"status": "unknown", "verified": False, "independent": False,
               "reason": "Research verification does not prove functional verification of this solution."}
    result = {node: dict(unknown) for node in identifiers}
    if not identifiers:
        return result
    with canvas.reading(project):
        repo = ChangesetRepository(canvas.db_for(project), project, workspace)
        head = repo.head()
        if head is None:
            return result
        accepted = repo.read(head)
        manifest_id = accepted.get("graphManifestId")
        graph = combined(GraphProposals(repo.db, project, workspace).read(manifest_id, manifest=True)) if manifest_id else None
        documents = {doc["nodeId"]: doc for doc in accepted["documents"]}
        entries = attach(repo.db, project, workspace, [{"nodeId": node} for node in identifiers], accepted["documents"], head)
        for entry in entries:
            node = entry["nodeId"]
            proof = entry["progressEvidence"].get("verification")
            if not proof:
                continue
            try:
                if graph is None:
                    raise ValueError("The solution has no accepted graph snapshot.")
                relevant, pinned = _inputs(graph, node)
                _, displayed = _inputs(view["graph"], node)
                if pinned != displayed:
                    raise ValueError("Displayed solution or collaboration inputs differ from the accepted graph.")
                for identifier in relevant:
                    document = documents.get(identifier)
                    live = canvas.node_spec(project, workspace, identifier)
                    if document is None or live["fields"] != document["fields"]:
                        raise ValueError("Displayed solution specification differs from the accepted contract.")
                require_accepted_content(canvas, project, workspace, head, relevant, view["graph"])
                execution = Executions(repo.db, project, workspace).read(proof["executionId"])
                _rules(canvas, project, workspace, execution, relevant, view["graph"])
                result[node] = {**proof, "status": "reported_evidence", "graphDigest": view["digest"],
                                "graphManifestId": manifest_id, "workspaceId": workspace}
            except ValueError as error:
                result[node] = {**unknown, "status": "unproven", "reason": str(error)}
    return result
