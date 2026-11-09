"""Selective semantic comparison for pinned evidence; presentation changes preserve proof."""
from backend.canvas.opora_graph_records import combined
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_graph_proposals import GraphProposals
from database.repositories.opora_content_records import ContentRecords

NODE_KEYS = ("kind", "purpose", "element", "site", "factRefs", "scenario", "checks", "goal_mode", "sourceRef")


def _node(node):
    result = {key: node[key] for key in NODE_KEYS if key in node}
    if node.get("design"):
        result["design"] = {key: node["design"][key] for key in ("artifactUrl", "version") if key in node["design"]}
    if node.get("card"):
        result["card"] = {key: node["card"][key] for key in ("states", "tech", "section") if key in node["card"]}
    return result


def input_closure(graph, roots):
    """Direct collaboration plus requirements inherited by every selected target.

    Ancestors contribute constraints, not sibling collaboration branches. Keeping
    this selection shared prevents search proof from drifting from execution proof.
    """
    by_node = {node["id"]: node for node in graph["nodes"]}
    dependencies = [edge for edge in graph["edges"] if edge.get("relation") in ("requires", "uses", "communicates_with")]
    relevant = set(roots)
    while True:
        contexts = set(relevant)
        for identifier in relevant:
            parent, seen = by_node.get(identifier, {}).get("parentId"), set()
            while parent and parent not in seen:
                seen.add(parent)
                contexts.add(parent)
                parent = by_node.get(parent, {}).get("parentId")
        selected = [edge for edge in dependencies if edge["source"] in relevant
                    or edge.get("relation") == "requires" and edge["source"] in contexts]
        added = {edge["target"] for edge in selected} - relevant
        if not added:
            return relevant, contexts, selected
        relevant.update(added)


def _snapshot(db, project, workspace, accepted, roots):
    graph = {"nodes": [], "edges": []}
    if accepted.get("graphManifestId"):
        graph = combined(GraphProposals(db, project, workspace).read(accepted["graphManifestId"], manifest=True))
    relevant, _, dependencies = input_closure(graph, roots)
    documents = {doc["nodeId"]: {"ownerWorkspace": doc["ownerWorkspace"], "fields": doc["fields"]}
                 for doc in accepted["documents"] if doc["nodeId"] in relevant}
    if not set(roots) <= set(documents):
        raise ValueError("Relevant evidence specifications are missing from the accepted revision.")
    by_node = {node["id"]: node for node in graph["nodes"]}
    nodes = {node["id"]: _node(node) for node in graph["nodes"] if node["id"] in relevant}
    edges = {edge["id"]: {key: edge[key] for key in ("source", "target", "relation", "requirement") if key in edge}
             for edge in dependencies}
    content = ContentRecords(db, project, workspace).read(accepted["contentManifestId"], manifest=True)["entries"] \
        if accepted.get("contentManifestId") else []
    all_documents = {doc["nodeId"]: doc for doc in accepted["documents"]}
    inherited = {}
    for node in relevant:
        ancestors, seen = [], set()
        parent = by_node.get(node, {}).get("parentId")
        while parent and parent not in seen:
            seen.add(parent)
            ancestor = by_node.get(parent, {})
            fields = all_documents.get(parent, {}).get("fields", {})
            rules = [item for item in content if item["kind"] == "config" and item["target"] == parent and item["field"] == "rules" and item["value"]]
            meaning = {"node": _node(ancestor), "fields": {key: value for key, value in fields.items() if value}, "rules": rules}
            # Missing accepted rule snapshots make a changed inherited scope unprovable.
            if not accepted.get("contentManifestId"):
                meaning["unresolvedRuleScope"] = parent
            if any(meaning.values()):
                ancestors.append(meaning)
            parent = ancestor.get("parentId")
        inherited[node] = ancestors
    own_content = [item for item in content if item["target"] in relevant]
    return {"documents": documents, "nodes": nodes, "dependencies": edges, "content": own_content, "inherited": inherited}


def semantic_compatible(db, project, workspace, pinned_revision, nodes):
    """Raise ValueError if relevant accepted specs or dependency contracts changed; return current accepted ID.

    Names and positions are presentation. Moves retain proof only when inherited constraints
    can be compared and remain equal. Test commands, element roles, content, source contracts
    and transitive collaboration/input definitions are semantic. Unrelated branches
    never enter this snapshot. The evidence continues identifying its original pinned revision.
    """
    repo = ChangesetRepository(db, project, workspace)
    current = repo.head()
    if current is None:
        raise ValueError("No accepted specification for evidence comparison.")
    pinned = repo.read(pinned_revision)
    latest = repo.read(current)
    if _snapshot(db, project, workspace, pinned, nodes) != _snapshot(db, project, workspace, latest, nodes):
        raise ValueError("Relevant accepted specifications or dependency contracts changed.")
    return current
