"""Bounded proof that an accepted target scope stayed unchanged across revisions."""
import re

from backend.canvas.graph import digest
from backend.canvas.opora_content_execution import selected_content
from backend.canvas.opora_graph_records import combined
from backend.editor.agent_packet.specification_scope import project_graph, select_scope
from database.repositories.opora_changesets import ChangesetRepository
from database.repositories.opora_graph_proposals import GraphProposals

_REVISION_ID = re.compile(r"[a-f0-9]{40}\Z")


def _read_revision_projection(db, repo, project, workspace, revision_id, node_id):
    try:
        record = repo.read(revision_id)
        manifest_id = record.get("graphManifestId")
        if not manifest_id:
            raise ValueError("Accepted revision has no graph manifest")
        manifest = GraphProposals(db, project, workspace).read(manifest_id, manifest=True)
        graph = combined(manifest)
        selection = select_scope(graph, node_id)
        selected_ids = set(selection["cardIds"])
        by_node = {}
        for document in record["documents"]:
            card_id = document["nodeId"]
            if card_id in by_node:
                raise ValueError("Accepted revision contains duplicate documents")
            by_node[card_id] = document
        if not selected_ids <= by_node.keys():
            raise ValueError("Accepted revision is missing a selected card document")
        projection = {
            "selection": selection,
            "graph": project_graph(graph, selection, redact=False),
            "documents": sorted((by_node[card_id] for card_id in selected_ids),
                                 key=lambda item: item["nodeId"]),
            "content": selected_content(db, project, workspace, record, selected_ids),
        }
        return record, digest(projection)
    except ValueError:
        raise
    except (TypeError, AttributeError, KeyError, IndexError, RecursionError) as exc:
        raise ValueError("Invalid accepted lineage record") from exc


def validate_accepted_lineage(db, project, workspace, node_id, origin, current, *, max_steps=256):
    """Validate a target's accepted projection at every revision from origin to current.

    The caller owns locking and snapshot consistency. This function only reads the database.
    """
    if type(max_steps) is not int or not 1 <= max_steps <= 256:
        raise ValueError("max_steps must be an integer from 1 through 256")
    if any(not isinstance(value, str) or _REVISION_ID.fullmatch(value) is None
           for value in (origin, current)):
        raise ValueError("Accepted revision IDs must be lowercase 40-character hex strings")

    repo = ChangesetRepository(db, project, workspace)
    if repo.head() != current:
        raise ValueError("Current accepted revision is not the workspace head")

    backwards = []
    seen = set()
    revision_id = current
    while True:
        if revision_id in seen:
            raise ValueError("Accepted revision ancestry contains a cycle")
        if len(backwards) >= max_steps:
            raise ValueError("Accepted revision ancestry exceeds the configured bound")
        seen.add(revision_id)
        record, projection_digest = _read_revision_projection(db, repo, project, workspace,
                                                              revision_id, node_id)
        backwards.append((revision_id, projection_digest))
        if revision_id == origin:
            break
        parent = record.get("parentRevision")
        if parent is None:
            raise ValueError("Origin is not an ancestor of the current accepted revision")
        if not isinstance(parent, str) or _REVISION_ID.fullmatch(parent) is None:
            raise ValueError("Accepted revision has an invalid parent revision")
        revision_id = parent

    backwards.reverse()
    scoped_digest = backwards[0][1]
    if any(digest != scoped_digest for _, digest in backwards[1:]):
        raise ValueError("Accepted target scope changed within the revision lineage")
    checked = [identifier for identifier, _ in backwards]
    return {
        "acceptedScopeUnchanged": True,
        "originAcceptedRevision": origin,
        "checkedAcceptedRevision": current,
        "scopedAcceptedDigest": scoped_digest,
        "checkedRevisions": checked,
        "checkedCount": len(checked),
    }
