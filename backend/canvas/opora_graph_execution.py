"""Conservative whole-graph acceptance guard before execution assignment capture."""
from backend.canvas.graph import digest
from backend.canvas.opora_graph_records import accepted_record, combined
from backend.editor.agent_packet.specification_context import _navigation, _node
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_graph_proposals import GraphProposals


def semantic_graph(graph):
    """Same semantics as capture, before redaction can collapse different secret values."""
    return {"nodes": [_node(node, graph["nodes"]) for node in sorted(graph["nodes"], key=lambda item: item["id"])],
            "edges": sorted(graph["edges"], key=lambda item: item["id"]), "navigation": _navigation(graph["nodes"])}


def require_accepted_graph(canvas, project, workspace, accepted_head, graph):
    # A steady block passes the same view graph for every card: verify it once per block (same object).
    def check():
        _require(canvas, project, workspace, accepted_head, graph)
        return graph

    if canvas.steady_value(project, ("accepted_graph", workspace, accepted_head), check) is not graph:
        _require(canvas, project, workspace, accepted_head, graph)


def _require(canvas, project, workspace, accepted_head, graph):
    repo = ChangesetRepository(canvas.db_for(project), project, workspace)
    accepted = accepted_record(repo, accepted_head)
    manifest_id = accepted.get("graphManifestId")
    if manifest_id is None:
        return  # Historical revisions explicitly accepted specifications only.
    manifest = GraphProposals(repo.db, project, workspace).read(manifest_id, manifest=True)
    if digest(semantic_graph(graph)) != digest(semantic_graph(combined(manifest))):
        raise ValueError("Working graph differs from the accepted graph; review graph changes before execution.")
